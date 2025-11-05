import json
import time
import uuid
import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.core.redis_manager import get_redis
from app.ws.room_manager import RoomManager
from app.ws.schemas import (
    EventPayload,
    HostCreateSession,
    PlayerJoin,
    PlayerAnswer,
    ServerStateSync,
    FinishedSessionSnapshot,
)

ws_router = APIRouter()
manager = RoomManager()


@ws_router.websocket("/ws")
async def ws_endpoint(
    websocket: WebSocket,
    role: str = Query(regex="^(host|player)$"),
    roomCode: str = Query(...),
    name: str | None = None,
    playerId: str | None = Query(default=None),
) -> None:
    print("\n" + "=" * 60)
    print("Новий WebSocket запит:")
    print(f" Role: {role}")
    print(f" RoomCode: {roomCode}")
    print(f" Name: {name}")
    print("=" * 60 + "\n")

    r = await get_redis()
    await manager.register(roomCode, websocket)

    player_id: str | None = None
    player_name: str | None = None

    session_key = f"session:{roomCode}"

    try:
        if role == "player":
            print(f"Обробка підключення PLAYER: {name}")

            # Перевірка, чи існує сесія
            session_raw = await r.get(session_key)
            session_exists = session_raw is not None
            print(f" Перевірка сесії {session_key}: {'EXISTS' if session_exists else 'NOT FOUND'}")

            if not session_exists:
                error_msg = "Вікторина не знайдена або ще не створена"
                print(error_msg)
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "message": error_msg,
                        }
                    )
                )
                await websocket.close()
                return

            session_data = json.loads(session_raw)
            if session_data.get("phase") == "ENDED":
                error_msg = "Вікторина вже завершена"
                print(error_msg)
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "message": error_msg,
                        }
                    )
                )
                await websocket.close()
                return

            # Відновлення або створення player_id
            # 1. Пробуємо взяти з query playerId
            if playerId is not None:
                stored_name = await r.hget(manager.k_players(roomCode), playerId)
                if stored_name is not None:
                    player_id = playerId
                    player_name = stored_name
                    print(f"Відновлено гравця за playerId={player_id[:8]}")
                else:
                    print("Переданий playerId не знайдено в Redis, буде створено нового гравця")

            # 2. Якщо player_id досі немає, пробуємо знайти за ім'ям
            if player_id is None and name:
                all_players = await r.hgetall(manager.k_players(roomCode))
                for pid, pname in all_players.items():
                    if pname == name:
                        player_id = pid
                        player_name = pname
                        print(f"Відновлено гравця за ім'ям, player_id={player_id[:8]}")
                        break

            # 3. Якщо нічого не знайшли, створюємо нового
            if player_id is None:
                player_id = str(uuid.uuid4())
                player_name = name or "Player"
                print(f"Створено нового player_id: {player_id[:8]}")

            # Записуємо гравця в Redis (оновлюємо ім'я, якщо змінилось)
            print(f"Зберігаємо в Redis: {manager.k_players(roomCode)}")
            await r.hset(manager.k_players(roomCode), mapping={player_id: player_name})
            await r.expire(manager.k_players(roomCode), 6 * 60 * 60)

            # Надсилаємо поточний стан гравцю
            state = await manager.get_state(r, roomCode)
            questions = await manager.load_questions(r, roomCode)
            qidx = state.get("questionIndex", -1)
            question = questions[qidx] if 0 <= qidx < len(questions) else None

            print(f"Поточний стан: phase={state.get('phase')}, qidx={qidx}")

            ss = ServerStateSync(
                roomCode=roomCode,
                phase=state.get("phase", "LOBBY"),
                questionIndex=qidx,
                startedAt=state.get("startedAt"),
                durationMs=state.get("durationMs"),
                question=question,
                scoreboard=await manager.scoreboard(r, roomCode)
                if state.get("phase") in ("REVEAL", "ENDED")
                else None,
                reveal=None,
                playerId=player_id,
            )

            print("Надсилаємо state_sync гравцю")
            await websocket.send_text(ss.model_dump_json())

            # Повідомляємо тільки інших (не самого гравця)
            print("Broadcast player_joined до інших (exclude self)")
            await manager.broadcast(
                roomCode,
                {
                    "type": "player_joined",
                    "playerName": player_name,
                    "playerId": player_id,
                    "roomCode": roomCode,
                },
                exclude=websocket,
            )

            print(f"Гравець {player_name} успішно підключений")

        elif role == "host":
            print(f"Обробка підключення HOST для кімнати: {roomCode}")

            # Надсилаємо поточний стан ведучому (включно зі scoreboard)
            state = await manager.get_state(r, roomCode)
            questions = await manager.load_questions(r, roomCode)
            qidx = state.get("questionIndex", -1)
            question = questions[qidx] if 0 <= qidx < len(questions) else None

            sb = await manager.scoreboard(r, roomCode)
            print(f"Поточний scoreboard для ведучого: {len(sb)} гравців")

            ss = ServerStateSync(
                roomCode=roomCode,
                phase=state.get("phase", "LOBBY"),
                questionIndex=qidx,
                startedAt=state.get("startedAt"),
                durationMs=state.get("durationMs"),
                question=question,
                scoreboard=sb,
                reveal=None,
                playerId=None,
            )

            print(f"Надсилаємо state_sync ведучому з {len(sb)} учасниками")
            await websocket.send_text(ss.model_dump_json())
            print("Ведучий успішно підключений")

        # Основний цикл подій
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            t = data.get("type")

            print(f"\nОтримано подію: {t} від {role}")

            # === Ведучий створює live-сесію ===
            if t == "host:create_session":
                print("Створення сесії")
                evt = HostCreateSession(**data)
                quiz_id = data.get("quizId")
                questions = [q.model_dump() for q in evt.questions]

                print(f" QuizId: {quiz_id}")
                print(f" Questions: {len(questions)}")

                # Якщо питань немає — підтягнути з бази
                if not questions and quiz_id:
                    print("Завантаження питань з БД")
                    try:
                        from app.services.quiz_service import QuizService

                        svc = QuizService()
                        quiz_data = svc.get_quiz(quiz_id)
                        questions = quiz_data["questions"]
                        print(f"Завантажено {len(questions)} питань")
                    except Exception as e:
                        error_msg = f"Помилка отримання питань за quizId: {str(e)}"
                        print(error_msg)
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "error",
                                    "message": error_msg,
                                }
                            )
                        )
                        continue

                # Генеруємо унікальний sessionId та час створення
                session_id = str(uuid.uuid4())
                created_at_ms = int(time.time() * 1000)

                # Зберігаємо повну сесію в Redis
                session_data = {
                    "sessionId": session_id,
                    "roomCode": roomCode,
                    "quizId": quiz_id,
                    "questions": questions,
                    "phase": "LOBBY",
                    "questionIndex": -1,
                    "players": [],
                    "createdAt": created_at_ms,
                }
                await r.set(session_key, json.dumps(session_data))
                print(f"Збережено {session_key} з sessionId={session_id}")

                # Викликаємо створення кімнати
                await manager.create_session(r, roomCode, questions, session_id, created_at_ms)

                # Розсилаємо поточний стан усім
                state = await manager.get_state(r, roomCode)
                out = ServerStateSync(
                    roomCode=roomCode,
                    phase=state["phase"],
                    questionIndex=state["questionIndex"],
                    startedAt=None,
                    durationMs=None,
                    question=None,
                    scoreboard=[],
                    reveal=None,
                    playerId=None,
                )

                print("Broadcast state_sync до всіх")
                await manager.broadcast(roomCode, json.loads(out.model_dump_json()))

            # === Початок питання (host:next_question) ===
            elif t == "host:next_question":
                print("Запуск наступного питання")
                duration_ms = data.get("durationMs", 30000)
                print(f" Тривалість: {duration_ms}ms")

                state = await manager.get_state(r, roomCode)
                current_idx = state.get("questionIndex", -1)
                next_idx = current_idx + 1

                print(f"Поточний індекс: {current_idx}")
                print(f"Наступний індекс: {next_idx}")

                questions = await manager.load_questions(r, roomCode)
                if next_idx >= len(questions):
                    error_msg = "Це було останнє питання"
                    print(error_msg)
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "message": error_msg,
                            }
                        )
                    )
                    continue

                msg = await manager.start_question(r, roomCode, next_idx, duration_ms)
                print("Broadcast question_started")
                await manager.broadcast(roomCode, msg)
                
            
            # === Розкриття відповіді ===
            elif t == "host:reveal_answer":
                print("Розкриття відповіді")
                state = await manager.get_state(r, roomCode)
                current_idx = state.get("questionIndex", -1)
                print(f" Індекс питання: {current_idx}")

                msg = await manager.reveal_answer(r, roomCode, current_idx)
                sb = await manager.scoreboard(r, roomCode)
                msg["scoreboard"] = sb

                print(f"Broadcast answer_revealed з scoreboard ({len(sb)} гравців)")
                await manager.broadcast(roomCode, msg)

            # === Завершення сесії ===
            elif t == "host:end_session":
                print("Завершення сесії")

                # Встановлюємо фазу ENDED у state
                state_before = await manager.get_state(r, roomCode)
                await manager.set_state(r, roomCode, phase="ENDED")
                sb = await manager.scoreboard(r, roomCode)

                # Читаємо та оновлюємо дані сесії
                session_raw = await r.get(session_key)
                session_data = json.loads(session_raw) if session_raw else {}
                session_id = session_data.get("sessionId") or str(uuid.uuid4())
                quiz_id = session_data.get("quizId")
                created_at_ms = session_data.get("createdAt") or int(time.time() * 1000)
                ended_at_ms = int(time.time() * 1000)

                session_data["sessionId"] = session_id
                session_data["quizId"] = quiz_id
                session_data["createdAt"] = created_at_ms
                session_data["phase"] = "ENDED"
                session_data["endedAt"] = ended_at_ms
                await r.set(session_key, json.dumps(session_data))

                questions = await manager.load_questions(r, roomCode)

                snapshot = FinishedSessionSnapshot(
                    sessionId=session_id,
                    roomCode=roomCode,
                    quizId=quiz_id,
                    createdAt=created_at_ms,
                    endedAt=ended_at_ms,
                    questions=questions,
                    scoreboard=sb,
                )

                archive_key = f"quiz:session:{session_id}"
                await r.set(archive_key, snapshot.model_dump_json())
                await r.zadd("quiz:session:index", {session_id: ended_at_ms})
                await r.sadd(f"quiz:room_sessions:{roomCode}", session_id)

                print(f"Збережено архів сесії в {archive_key}")

                # Очищаємо оперативні дані кімнати
                await manager.cleanup_room_data(r, roomCode)

                print("Broadcast session_ended")
                await manager.broadcast(
                    roomCode,
                    {
                        "type": "session_ended",
                        "scoreboard": sb,
                        "sessionId": session_id,
                    },
                )

            # === Гравець явно приєднується (застаріле, але підтримується) ===
            elif t == "player:join":
                print("Явне приєднання гравця (legacy)")
                evt = PlayerJoin(**data)

                if player_id is None:
                    player_id = str(uuid.uuid4())
                    player_name = evt.name
                    print(f" Створено новий player_id: {player_id[:8]}")

                    await r.hset(manager.k_players(roomCode), mapping={player_id: evt.name})
                    await r.expire(manager.k_players(roomCode), 6 * 60 * 60)

                # Підтвердження гравцю
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "player_joined",
                            "playerId": player_id,
                            "playerName": evt.name,
                        }
                    )
                )

                # Повідомлення всім іншим (не собі)
                print("Broadcast player_joined (exclude self)")
                await manager.broadcast(
                    roomCode,
                    {
                        "type": "player_joined",
                        "playerName": evt.name,
                        "playerId": player_id,
                    },
                    exclude=websocket,
                )

            # === Гравець відповідає ===
            elif t == "player:answer":
                print("Відповідь гравця")
                evt = PlayerAnswer(**data)

                if player_id is None:
                    error_msg = "Player not registered"
                    print(error_msg)
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "message": error_msg,
                            }
                        )
                    )
                    continue

                print(f" Player: {player_id[:8]}")
                print(f" Question: {evt.questionIndex}, Option: {evt.optionIndex}")

                ok = await manager.submit_answer(
                    r,
                    roomCode,
                    evt.questionIndex,
                    player_id,
                    evt.optionIndex,
                )

                print(f" Результат: {'OK' if ok else 'REJECTED'}")

                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "answer_ack",
                            "ok": ok,
                        }
                    )
                )

            # === Невідомий тип події ===
            else:
                error_msg = f"Невідомий тип події: {t}"
                print(error_msg)
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "message": error_msg,
                        }
                    )
                )

    except WebSocketDisconnect:
        print(f"\nВідключення: {role} ({player_name or 'host'}) від {roomCode}")
        # Більше не розсилаємо player_left, щоб перезавантаження сторінки
        # одного гравця не впливало на інших

    except Exception as e:
        print(f"\nПомилка WebSocket: {str(e)}")
        import traceback

        traceback.print_exc()
        try:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "message": str(e),
                    }
                )
            )
        except Exception:
            pass

    finally:
        print(f"Cleanup для {role} ({player_name or 'host'})")
        await manager.unregister(roomCode, websocket)
        # Гравця з Redis більше не видаляємо тут, щоб дозволити повторне підключення
