import json
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.redis_manager import get_redis
from app.ws.room_manager import RoomManager
from app.ws.schemas import (
    EventPayload, HostCreateSession, HostStartQuestion,
    HostRevealAnswer, HostNextQuestion, HostEndSession,
    PlayerJoin, PlayerAnswer, ServerStateSync
)

ws_router = APIRouter()
manager = RoomManager()

@ws_router.websocket("/ws")
async def ws_endpoint(
    websocket: WebSocket,
    role: str = Query(regex="^(host|player)$"),
    roomCode: str = Query(...),
    name: str | None = None,
):
    print(f"\n{'='*60}")
    print(f"Новий WebSocket запит:")
    print(f"   Role: {role}")
    print(f"   RoomCode: {roomCode}")
    print(f"   Name: {name}")
    print(f"{'='*60}\n")
    
    r = await get_redis()
    await manager.register(roomCode, websocket)

    player_id: str | None = None
    player_name: str | None = None

    try:
        if role == "player":
            print(f"Обробка підключення PLAYER: {name}")
            
            # Перевірка, чи існує сесія
            session_key = f"session:{roomCode}"
            session_exists = await r.exists(session_key)
            
            print(f"   Перевірка сесії {session_key}: {'EXISTS' if session_exists else 'NOT FOUND'}")
            
            if not session_exists:
                error_msg = "Вікторина не знайдена або ще не створена"
                print(f"{error_msg}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": error_msg
                }))
                await websocket.close()
                return

            # Автоматичне додавання гравця при підключенні
            player_id = str(uuid.uuid4())
            player_name = name or "Player"
            
            print(f"Створено player_id: {player_id[:8]}...")
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
            )
            
            print(f"Надсилаємо state_sync гравцю")
            await websocket.send_text(ss.model_dump_json())

            # Повідомляємо ТІЛЬКИ ІНШИХ (не самого гравця!)
            print(f" Broadcast player_joined до інших (exclude self)")
            await manager.broadcast(roomCode, {
                "type": "player_joined",
                "playerName": player_name,
                "playerId": player_id,
                "roomCode": roomCode
            }, exclude=websocket)  
            
            print(f"Гравець {player_name} успішно підключений\n")

        elif role == "host":
            print(f"Обробка підключення HOST для кімнати: {roomCode}")
            
            # Надсилаємо поточний стан ведучому (включно зі scoreboard)
            state = await manager.get_state(r, roomCode)
            questions = await manager.load_questions(r, roomCode)
            qidx = state.get("questionIndex", -1)
            question = questions[qidx] if 0 <= qidx < len(questions) else None
            
            # ЗАВЖДИ надсилаємо scoreboard ведучому
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
            )
            
            print(f"Надсилаємо state_sync ведучому з {len(sb)} учасниками")
            await websocket.send_text(ss.model_dump_json())
            print(f"Ведучий успішно підключений\n")

        # 🔹 Основний цикл подій
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            t = data.get("type")
            
            print(f"\nОтримано подію: {t} від {role}")

            # === Ведучий створює live-сесію ===
            if t == "host:create_session":
                print(f"Створення сесії...")
                evt = HostCreateSession(**data)
                quiz_id = data.get("quizId")
                questions = [q.model_dump() for q in evt.questions]

                print(f"   QuizId: {quiz_id}")
                print(f"   Questions: {len(questions)}")

                # Якщо питань немає — підтягнути з бази
                if not questions and quiz_id:
                    print(f"Завантаження питань з БД...")
                    try:
                        from app.services.quiz_service import QuizService
                        svc = QuizService()
                        quiz_data = svc.get_quiz(quiz_id)
                        questions = quiz_data["questions"]
                        print(f"Завантажено {len(questions)} питань")
                    except Exception as e:
                        error_msg = f"Помилка отримання питань за quizId: {str(e)}"
                        print(f"{error_msg}")
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": error_msg
                        }))
                        continue

                # Зберігаємо повну сесію в Redis
                session_data = {
                    "quizId": quiz_id,
                    "questions": questions,
                    "phase": "LOBBY",
                    "questionIndex": -1,
                    "players": [],
                }
                await r.set(f"session:{roomCode}", json.dumps(session_data))
                print(f"Збережено session:{roomCode}")

                # Викликаємо створення кімнати
                await manager.create_session(r, roomCode, questions)

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
                )
                
                print(f"Broadcast state_sync до всіх")
                await manager.broadcast(roomCode, json.loads(out.model_dump_json()))

            # === Початок питання (host:next_question) ===
            elif t == "host:next_question":
                print(f"Запуск наступного питання...")
                
                duration_ms = data.get("durationMs", 30000)
                print(f"   Тривалість: {duration_ms}ms")
                
                state = await manager.get_state(r, roomCode)
                current_idx = state.get("questionIndex", -1)
                next_idx = current_idx + 1
                
                print(f"Поточний індекс: {current_idx}")
                print(f"Наступний індекс: {next_idx}")
                
                questions = await manager.load_questions(r, roomCode)
                if next_idx >= len(questions):
                    error_msg = "Це було останнє питання"
                    print(f" {error_msg}")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": error_msg
                    }))
                    continue
                
                msg = await manager.start_question(r, roomCode, next_idx, duration_ms)
                print(f"Broadcast question_started")
                await manager.broadcast(roomCode, msg)

            # === Розкриття відповіді ===
            elif t == "host:reveal_answer":
                print(f"Розкриття відповіді...")
                
                state = await manager.get_state(r, roomCode)
                current_idx = state.get("questionIndex", -1)
                
                print(f"   Індекс питання: {current_idx}")
                
                msg = await manager.reveal_answer(r, roomCode, current_idx)
                sb = await manager.scoreboard(r, roomCode)
                msg["scoreboard"] = sb
                
                print(f"Broadcast answer_revealed з scoreboard ({len(sb)} гравців)")
                await manager.broadcast(roomCode, msg)

            # === Завершення сесії ===
            elif t == "host:end_session":
                print(f"Завершення сесії...")
                
                await manager.set_state(r, roomCode, phase="ENDED")
                sb = await manager.scoreboard(r, roomCode)
                
                print(f"Broadcast session_ended")
                await manager.broadcast(roomCode, {
                    "type": "session_ended", 
                    "scoreboard": sb
                })

            # === Гравець явно приєднується (застаріле, але підтримується) ===
            elif t == "player:join":
                print(f"Явне приєднання гравця (legacy)...")
                evt = PlayerJoin(**data)
                
                if player_id is None:
                    player_id = str(uuid.uuid4())
                    player_name = evt.name
                    print(f"   Створено новий player_id: {player_id[:8]}...")
                    
                await r.hset(manager.k_players(roomCode), mapping={player_id: evt.name})
                await r.expire(manager.k_players(roomCode), 6 * 60 * 60)
                
                # Підтвердження гравцю
                await websocket.send_text(json.dumps({
                    "type": "player_joined",
                    "playerId": player_id,
                    "playerName": evt.name
                }))
                
                # Повідомлення всім іншим (не собі!)
                print(f"Broadcast player_joined (exclude self)")
                await manager.broadcast(roomCode, {
                    "type": "player_joined",
                    "playerName": evt.name,
                    "playerId": player_id
                }, exclude=websocket)

            # === Гравець відповідає ===
            elif t == "player:answer":
                print(f"Відповідь гравця...")
                evt = PlayerAnswer(**data)
                
                if player_id is None:
                    error_msg = "Player not registered"
                    print(f"   {error_msg}")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": error_msg
                    }))
                    continue
                
                print(f"   Player: {player_id[:8]}...")
                print(f"   Question: {evt.questionIndex}, Option: {evt.optionIndex}")
                    
                ok = await manager.submit_answer(
                    r, roomCode, evt.questionIndex, player_id, evt.optionIndex
                )
                
                print(f"   Результат: {'OK' if ok else 'REJECTED'}")
                
                await websocket.send_text(json.dumps({
                    "type": "answer_ack", 
                    "ok": ok
                }))

            # === Невідомий тип події ===
            else:
                error_msg = f"Невідомий тип події: {t}"
                print(f"   {error_msg}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": error_msg
                }))

    except WebSocketDisconnect:
        print(f"\nВідключення: {role} ({player_name or 'host'}) від {roomCode}")
        
        # Якщо гравець відключився - повідомити інших
        if role == "player" and player_name:
            try:
                print(f"  Broadcast player_left")
                await manager.broadcast(roomCode, {
                    "type": "player_left",
                    "playerName": player_name,
                    "playerId": player_id
                }, exclude=websocket)
            except Exception as e:
                print(f" Помилка broadcast: {str(e)}")
                
    except Exception as e:
        print(f"\nПомилка WebSocket: {str(e)}")
        import traceback
        traceback.print_exc()
        
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e)
            }))
        except:
            pass
        
    finally:
        print(f"Cleanup для {role} ({player_name or 'host'})")
        await manager.unregister(roomCode, websocket)
        
        # Видаляємо гравця з Redis при відключенні
        if player_id and role == "player":
            try:
                await r.hdel(manager.k_players(roomCode), player_id)
                print(f" Видалено гравця з Redis")
            except Exception as e:
                print(f" Помилка видалення з Redis: {str(e)}")