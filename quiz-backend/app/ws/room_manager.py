import json
import time
from typing import Dict, Set
from fastapi.websockets import WebSocket
from redis.asyncio import Redis

REDIS_PREFIX = "quiz:room:"

class RoomManager:
    def __init__(self):
        # живі підключення (в межах одного інстанса)
        self.connections: Dict[str, Set[WebSocket]] = {}

    # --- Redis ключі ---
    def k_state(self, room: str) -> str:
        return f"{REDIS_PREFIX}{room}:state"
    def k_questions(self, room: str) -> str:
        return f"{REDIS_PREFIX}{room}:questions"
    def k_answers(self, room: str, qidx: int) -> str:
        return f"{REDIS_PREFIX}{room}:answers:q{qidx}"
    def k_players(self, room: str) -> str:
        return f"{REDIS_PREFIX}{room}:players"
    def k_score(self, room: str) -> str:
        return f"{REDIS_PREFIX}{room}:score"

    # --- підключення ---
    async def register(self, room: str, ws: WebSocket):
        await ws.accept()
        self.connections.setdefault(room, set()).add(ws)

    async def unregister(self, room: str, ws: WebSocket):
        try:
            self.connections.get(room, set()).discard(ws)
        except Exception:
            pass

    async def broadcast(self, room: str, message: dict):
        data = json.dumps(message)
        for ws in list(self.connections.get(room, set())):
            try:
                await ws.send_text(data)
            except Exception:
                await self.unregister(room, ws)

    # --- стан сесії ---
    async def create_session(self, r: Redis, room: str, questions: list[dict]):
        # зберігаємо список питань один раз
        await r.set(self.k_questions(room), json.dumps(questions))
        # початковий стан
        state = {
            "phase": "LOBBY",
            "questionIndex": -1,
            "startedAt": None,
            "durationMs": None
        }
        await r.set(self.k_state(room), json.dumps(state))
        # скидаємо службові структури
        await r.delete(self.k_score(room))
        # TTL на кімнату: 6 год
        await r.expire(self.k_questions(room), 6 * 60 * 60)
        await r.expire(self.k_state(room), 6 * 60 * 60)

    async def load_questions(self, r: Redis, room: str) -> list[dict]:
        raw = await r.get(self.k_questions(room))
        return json.loads(raw) if raw else []

    async def get_state(self, r: Redis, room: str) -> dict:
        raw = await r.get(self.k_state(room))
        return json.loads(raw) if raw else {}

    async def set_state(self, r: Redis, room: str, **patch):
        cur = await self.get_state(r, room)
        cur.update(patch)
        await r.set(self.k_state(room), json.dumps(cur))
        return cur

    async def start_question(self, r: Redis, room: str, qidx: int, duration_ms: int):
        now_ms = int(time.time() * 1000)
        await self.set_state(
            r, room,
            phase="QUESTION_ACTIVE",
            questionIndex=qidx,
            startedAt=now_ms,
            durationMs=duration_ms,
        )
        # очистити відповіді для цього питання
        await r.delete(self.k_answers(room, qidx))
        # подія клієнтам
        questions = await self.load_questions(r, room)
        question = questions[qidx] if 0 <= qidx < len(questions) else None
        return {
            "type": "question_started",
            "questionIndex": qidx,
            "startedAt": now_ms,
            "durationMs": duration_ms,
            "question": question,
        }

    async def submit_answer(self, r: Redis, room: str, qidx: int, player_id: str, option_index: int) -> bool:
        state = await self.get_state(r, room)
        if state.get("phase") != "QUESTION_ACTIVE":
            return False
        started = state.get("startedAt")
        dur = state.get("durationMs", 0)
        now_ms = int(time.time() * 1000)
        if started is None or now_ms > started + dur:
            return False
        # зберігаємо першу відповідь гравця; повторні ігноруємо
        key = self.k_answers(room, qidx)
        exists = await r.hexists(key, player_id)
        if exists:
            return False
        await r.hset(key, mapping={player_id: str(option_index)})
        await r.expire(key, 6 * 60 * 60)
        return True

    async def reveal_answer(self, r: Redis, room: str, qidx: int):
        # рахуємо результати для питання
        questions = await self.load_questions(r, room)
        question = questions[qidx]
        correct_idx = int(question["correct_answer"])  # 0..3
        answers = await r.hgetall(self.k_answers(room, qidx))
        # оновлюємо скорборд
        for player_id, opt in answers.items():
            if int(opt) == correct_idx:
                await r.zincrby(self.k_score(room), 1, player_id)
        await r.expire(self.k_score(room), 6 * 60 * 60)
        await self.set_state(r, room, phase="REVEAL")
        # агрегат для фронта
        counts = {"0": 0, "1": 0, "2": 0, "3": 0}
        for opt in answers.values():
            counts[str(opt)] = counts.get(str(opt), 0) + 1
        return {
            "type": "answer_revealed",
            "questionIndex": qidx,
            "correctIndex": correct_idx,
            "distribution": {int(k): v for k, v in counts.items()}
        }

    async def scoreboard(self, r: Redis, room: str) -> list[dict]:
        # повертаємо ТОП у довільному порядку; імена тримаємо в Hash players
        z = await r.zrevrange(self.k_score(room), 0, -1, withscores=True)
        names = await r.hgetall(self.k_players(room))
        return [
            {"playerId": pid, "name": names.get(pid, pid), "score": int(score)}
            for pid, score in z
        ]