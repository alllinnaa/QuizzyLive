import json
import time
import uuid
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from pydantic import ValidationError
from app.core.redis_manager import get_redis
from app.ws.room_manager import RoomManager
from app.ws.schemas import (
    EventPayload,
    HostCreateSession,
    HostStartQuestion,
    HostRevealAnswer,
    HostNextQuestion,
    HostEndSession,
    PlayerJoin,
    PlayerAnswer,
    ServerStateSync,
    FinishedSessionSnapshot,
)
from app.services.quiz_session_service import QuizSessionService

ws_router = APIRouter()
manager = RoomManager()


async def send_error(websocket: WebSocket, message: str) -> None:
    """Допоміжна функція для надсилання помилок"""
    await websocket.send_text(
        json.dumps(
            {
                "type": "error",
                "message": message,
            }
        )
    )


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
            
            session_raw = await r.get(session_key)
            session_exists = session_raw is not None
            print(f" Перевірка сесії {session_key}: {'EXISTS' if session_exists else 'NOT FOUND'}")
            
            if not session_exists:
                error_msg = "Вікторина не знайдена або ще не створена"
                print(error_msg)
                await send_error(websocket, error_msg)
                await websocket.close()
                return

            session_data = json.loads(session_raw)
            if session_data.get("phase") == "ENDED":
                error_msg = "Вікторина вже завершена"
                print(error_msg)
                await send_error(websocket, error_msg)
                await websocket.close()
                return

            if playerId is not None:
                stored_name = await r.hget(manager.k_players(roomCode), playerId)
                if stored_name is not None:
                    player_id = playerId
                    player_name = stored_name
                    print(f"Відновлено гравця за playerId={player_id[:8]}")
                else:
                    print("Переданий playerId не знайдено в Redis")

            if player_id is None and name:
                all_players = await r.hgetall(manager.k_players(roomCode))
                for pid, pname in all_players.items():
                    if pname == name:
                        player_id = pid
                        player_name = pname
                        print(f"Відновлено гравця за ім'ям, player_id={player_id[:8]}")
                        break

            if player_id is None:
                player_id = str(uuid.uuid4())
                player_name = name or "Player"
                print(f"Створено нового player_id: {player_id[:8]}")

            await r.hset(
                manager.k_players(roomCode), mapping={player_id: player_name}
            )
            await r.expire(manager.k_players(roomCode), 6 * 60 * 60)

            state = await manager.get_state(r, roomCode)
            questions = await manager.load_questions(r, roomCode)
            qidx = state.get("questionIndex", -1)
            question = questions[qidx] if 0 <= qidx < len(questions) else None
            sb = await manager.scoreboard(r, roomCode)

            ss = ServerStateSync(
                roomCode=roomCode,
                phase=state.get("phase", "LOBBY"),
                questionIndex=qidx,
                startedAt=state.get("startedAt"),
                durationMs=state.get("durationMs"),
                question=question,
                scoreboard=sb,
                reveal=None,
                playerId=player_id,
            )
            
            print("Надсилаємо state_sync гравцю")
            await websocket.send_text(ss.model_dump_json())

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
            
            state = await manager.get_state(r, roomCode)
            questions = await manager.load_questions(r, roomCode)
            qidx = state.get("questionIndex", -1)
            question = questions[qidx] if 0 <= qidx < len(questions) else None
            sb = await manager.scoreboard(r, roomCode)

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

        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            event_type = data.get("type")
            
            print(f"\nОтримано подію: {event_type} від {role}")

            try:
                if event_type == "host:create_session":
                    evt = HostCreateSession(**data)
                    await handle_create_session(websocket, r, roomCode, evt, session_key)

                elif event_type == "host:start_question":
                    evt = HostStartQuestion(**data)
                    await handle_start_question(websocket, r, roomCode, evt)

                elif event_type == "host:next_question":
                    evt = HostNextQuestion(**data)
                    await handle_next_question(websocket, r, roomCode, evt)

                elif event_type == "host:reveal_answer":
                    evt = HostRevealAnswer(**data)
                    await handle_reveal_answer(websocket, r, roomCode, evt)

                elif event_type == "host:end_session":
                    evt = HostEndSession(**data)
                    await handle_end_session(websocket, r, roomCode, session_key)

                elif event_type == "player:join":
                    evt = PlayerJoin(**data)
                    await handle_player_join(
                        websocket, r, roomCode, evt, player_id, player_name
                    )

                elif event_type == "player:answer":
                    evt = PlayerAnswer(**data)
                    await handle_player_answer(websocket, r, roomCode, evt, player_id)

                else:
                    await send_error(websocket, f"Невідомий тип події: {event_type}")

            except ValidationError as e:
                error_msg = f"Помилка валідації даних: {str(e)}"
                print(error_msg)
                await send_error(websocket, error_msg)

    except WebSocketDisconnect:
        print(f"\nВідключення: {role} ({player_name or 'host'}) від {roomCode}")
    except Exception as e:
        print(f"\nПомилка WebSocket: {str(e)}")
        import traceback
        traceback.print_exc()
        try:
            await send_error(websocket, str(e))
        except Exception:
            pass
    finally:
        print(f"Cleanup для {role} ({player_name or 'host'})")
        await manager.unregister(roomCode, websocket)


async def handle_create_session(
    websocket: WebSocket,
    r,
    roomCode: str,
    evt: HostCreateSession,
    session_key: str,
) -> None:
    """Створення сесії"""
    print("Створення сесії")
    
    quiz_id = evt.quizId
    questions = [q.model_dump() for q in evt.questions]
    
    print(f" QuizId: {quiz_id}")
    print(f" Questions: {len(questions)}")

    if not questions and quiz_id:
        print("Завантаження питань з БД")
        try:
            from app.services.quiz_service import QuizService
            svc = QuizService()
            quiz_data = svc.get_quiz(quiz_id)
            questions = quiz_data["questions"]
            print(f"Завантажено {len(questions)} питань")
        except Exception as e:
            await send_error(websocket, f"Помилка отримання питань: {str(e)}")
            return

    session_id = str(uuid.uuid4())
    created_at_ms = int(time.time() * 1000)

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

    await manager.create_session(r, roomCode, questions, session_id, created_at_ms)

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


async def handle_start_question(
    websocket: WebSocket, r, roomCode: str, evt: HostStartQuestion
) -> None:
    """Запуск питання (застаріла подія, краще використовувати host:next_question)"""
    print(f"Запуск питання {evt.questionIndex} на {evt.durationMs}ms")
    
    msg = await manager.start_question(r, roomCode, evt.questionIndex, evt.durationMs)
    await manager.broadcast(roomCode, msg)


async def handle_next_question(
    websocket: WebSocket, r, roomCode: str, evt: HostNextQuestion
) -> None:
    """Перехід до наступного питання"""
    print("Запуск наступного питання")
    
    duration_ms = evt.durationMs
    print(f" Тривалість: {duration_ms}ms")

    state = await manager.get_state(r, roomCode)
    current_idx = state.get("questionIndex", -1)
    next_idx = current_idx + 1

    questions = await manager.load_questions(r, roomCode)
    
    if next_idx >= len(questions):
        await send_error(websocket, "Це було останнє питання")
        return

    msg = await manager.start_question(r, roomCode, next_idx, duration_ms)
    print("Broadcast question_started")
    await manager.broadcast(roomCode, msg)


async def handle_reveal_answer(
    websocket: WebSocket, r, roomCode: str, evt: HostRevealAnswer
) -> None:
    """Розкриття правильної відповіді"""
    print("Розкриття відповіді")
    
    state = await manager.get_state(r, roomCode)
    current_idx = evt.questionIndex or state.get("questionIndex", -1)
    
    print(f" Індекс питання: {current_idx}")

    msg = await manager.reveal_answer(r, roomCode, current_idx)
    sb = await manager.scoreboard(r, roomCode)
    msg["scoreboard"] = sb

    print(f"Broadcast answer_revealed з scoreboard ({len(sb)} гравців)")
    await manager.broadcast(roomCode, msg)


async def handle_end_session(
    websocket: WebSocket, r, roomCode: str, session_key: str
) -> None:
    """Завершення вікторини"""
    print("Завершення сесії")

    await manager.set_state(r, roomCode, phase="ENDED")
    sb = await manager.scoreboard(r, roomCode)

    session_raw = await r.get(session_key)
    session_data = json.loads(session_raw) if session_raw else {}
    
    session_id = session_data.get("sessionId") or str(uuid.uuid4())
    quiz_id = session_data.get("quizId")
    created_at_ms = session_data.get("createdAt") or int(time.time() * 1000)
    ended_at_ms = int(time.time() * 1000)

    session_data.update({
        "sessionId": session_id,
        "quizId": quiz_id,
        "createdAt": created_at_ms,
        "phase": "ENDED",
        "endedAt": ended_at_ms,
    })
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

    try:
        session_service = QuizSessionService()
        session_service.save_finished_session(snapshot.model_dump())
        print(f"Сесію {session_id} збережено в Supabase")
    except Exception as e:
        print(f"Помилка збереження сесії в Supabase: {e}")

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


async def handle_player_join(
    websocket: WebSocket,
    r,
    roomCode: str,
    evt: PlayerJoin,
    player_id: str | None,
    player_name: str | None,
) -> None:
    """Явне приєднання гравця (legacy підтримка)"""
    print("Явне приєднання гравця (legacy)")
    
    if player_id is None:
        player_id = str(uuid.uuid4())
        player_name = evt.name
        print(f" Створено новий player_id: {player_id[:8]}")

    await r.hset(manager.k_players(roomCode), mapping={player_id: evt.name})
    await r.expire(manager.k_players(roomCode), 6 * 60 * 60)

    await websocket.send_text(
        json.dumps(
            {
                "type": "player_joined",
                "playerId": player_id,
                "playerName": evt.name,
            }
        )
    )

    await manager.broadcast(
        roomCode,
        {
            "type": "player_joined",
            "playerName": evt.name,
            "playerId": player_id,
        },
        exclude=websocket,
    )


async def handle_player_answer(
    websocket: WebSocket,
    r,
    roomCode: str,
    evt: PlayerAnswer,
    player_id: str | None,
) -> None:
    """Обробка відповіді гравця"""
    print("Відповідь гравця")
    
    if player_id is None:
        await send_error(websocket, "Player not registered")
        return

    print(f" Player: {player_id[:8]}")
    print(f" Question: {evt.questionIndex}, Option: {evt.optionIndex}")

    ok = await manager.submit_answer(
        r, roomCode, evt.questionIndex, player_id, evt.optionIndex
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