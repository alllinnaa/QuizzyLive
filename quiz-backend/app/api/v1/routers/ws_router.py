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
    roomCode: str = Query(min_length=4, max_length=16),
    name: str | None = None,
):
    r = await get_redis()
    await manager.register(roomCode, websocket)

    player_id: str | None = None

    try:
        if role == "player":
            # авто-join при конекті, щоб зберегти ім'я
            player_id = str(uuid.uuid4())
            await r.hset(manager.k_players(roomCode), mapping={player_id: name or "Player"})
            await r.expire(manager.k_players(roomCode), 6 * 60 * 60)
            # віддати поточний стан
            state = await manager.get_state(r, roomCode)
            questions = await manager.load_questions(r, roomCode)
            qidx = state.get("questionIndex", -1)
            question = questions[qidx] if 0 <= qidx < len(questions) else None
            ss = ServerStateSync(
                roomCode=roomCode,
                phase=state.get("phase", "LOBBY"),
                questionIndex=qidx,
                startedAt=state.get("startedAt"),
                durationMs=state.get("durationMs"),
                question=question,
                scoreboard=await manager.scoreboard(r, roomCode) if state.get("phase") in ("REVEAL", "ENDED") else None,
                reveal=None,
            )
            await websocket.send_text(ss.model_dump_json())

        # цикл подій
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)

            # ВАЛІДАЦІЯ ВХІДНИХ ПОВІДОМЛЕНЬ
            evt: EventPayload
            t = data.get("type")
            if t == "host:create_session":
                evt = HostCreateSession(**data)
                await manager.create_session(r, roomCode, [q.model_dump() for q in evt.questions])
                # надсилаємо повний state_sync усім
                state = await manager.get_state(r, roomCode)
                out = ServerStateSync(
                    roomCode=roomCode, phase=state["phase"], questionIndex=state["questionIndex"],
                    startedAt=None, durationMs=None, question=None, scoreboard=[], reveal=None
                )
                await manager.broadcast(roomCode, json.loads(out.model_dump_json()))

            elif t == "host:start_question":
                evt = HostStartQuestion(**data)
                msg = await manager.start_question(r, roomCode, evt.questionIndex, evt.durationMs)
                await manager.broadcast(roomCode, msg)

            elif t == "host:reveal_answer":
                evt = HostRevealAnswer(**data)
                msg = await manager.reveal_answer(r, roomCode, evt.questionIndex)
                # додаємо скорборд
                sb = await manager.scoreboard(r, roomCode)
                msg["scoreboard"] = sb
                await manager.broadcast(roomCode, msg)

            elif t == "host:next_question":
                evt = HostNextQuestion(**data)
                # просто переведемо фазу в LOBBY до старту
                await manager.set_state(r, roomCode, phase="LOBBY", questionIndex=evt.questionIndex)
                await manager.broadcast(roomCode, {
                    "type": "next_question_ready",
                    "questionIndex": evt.questionIndex
                })

            elif t == "host:end_session":
                HostEndSession(**data)
                await manager.set_state(r, roomCode, phase="ENDED")
                sb = await manager.scoreboard(r, roomCode)
                await manager.broadcast(roomCode, {"type": "session_ended", "scoreboard": sb})

            elif t == "player:join":
                evt = PlayerJoin(**data)
                # якщо гравець явно надсилає join (дубль), оновимо ім'я
                if player_id is None:
                    player_id = str(uuid.uuid4())
                await r.hset(manager.k_players(roomCode), mapping={player_id: evt.name})
                await r.expire(manager.k_players(roomCode), 6 * 60 * 60)
                await websocket.send_text(json.dumps({"type": "join_ok", "playerId": player_id}))

            elif t == "player:answer":
                evt = PlayerAnswer(**data)
                if player_id is None:
                    player_id = str(uuid.uuid4())
                ok = await manager.submit_answer(r, roomCode, evt.questionIndex, player_id, evt.optionIndex)
                await websocket.send_text(json.dumps({"type": "answer_ack", "ok": ok}))

            else:
                await websocket.send_text(json.dumps({"type": "error", "message": "unknown event type"}))

    except WebSocketDisconnect:
        pass
    finally:
        await manager.unregister(roomCode, websocket)