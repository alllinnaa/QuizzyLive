import json
import time
from typing import Dict, Set, Optional
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
        """Реєструє WebSocket з'єднання в кімнаті"""
        await ws.accept()
        self.connections.setdefault(room, set()).add(ws)
        print(f"✅ Зареєстровано з'єднання в кімнаті {room}. Всього: {len(self.connections[room])}")

    async def unregister(self, room: str, ws: WebSocket):
        """Видаляє WebSocket з'єднання з кімнати"""
        try:
            if room in self.connections:
                self.connections[room].discard(ws)
                print(f"🔌 Видалено з'єднання з кімнати {room}. Залишилось: {len(self.connections[room])}")
                
                # Видаляємо кімнату якщо порожня
                if not self.connections[room]:
                    del self.connections[room]
                    print(f"🗑️ Кімната {room} видалена (немає з'єднань)")
        except Exception as e:
            print(f"⚠️ Помилка при видаленні з'єднання: {str(e)}")

    async def broadcast(self, room: str, message: dict, exclude: Optional[WebSocket] = None):
        """
        Розсилає повідомлення всім підключеним до кімнати.
        
        Args:
            room: Код кімнати
            message: Повідомлення (dict)
            exclude: WebSocket який треба виключити з розсилки (опціонально)
        """
        if room not in self.connections:
            print(f"⚠️ Кімната {room} не існує для broadcast")
            return
        
        connections = self.connections[room]
        message_type = message.get('type', 'unknown')
        print(f"📢 Broadcast до {room}: {message_type} ({len(connections)} з'єднань)")
        
        data = json.dumps(message)
        disconnected = []
        sent_count = 0
        
        for ws in list(connections):
            # Пропускаємо excluded WebSocket
            if exclude is not None and ws == exclude:
                print(f"  ⏭️ Пропускаємо excluded websocket")
                continue
            
            try:
                await ws.send_text(data)
                sent_count += 1
            except Exception as e:
                print(f"  ❌ Помилка відправки: {str(e)}")
                disconnected.append(ws)
        
        print(f"  ✅ Надіслано {sent_count} з {len(connections)} з'єднань")
        
        # Видаляємо відключені з'єднання
        for ws in disconnected:
            await self.unregister(room, ws)

    # --- стан сесії ---
    async def create_session(self, r: Redis, room: str, questions: list[dict]):
        """Створює нову сесію вікторини"""
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
        
        print(f"🎯 Створено сесію для кімнати {room} з {len(questions)} питаннями")

    async def load_questions(self, r: Redis, room: str) -> list[dict]:
        """Завантажує питання сесії з Redis"""
        raw = await r.get(self.k_questions(room))
        return json.loads(raw) if raw else []

    async def get_state(self, r: Redis, room: str) -> dict:
        """Отримує поточний стан сесії"""
        raw = await r.get(self.k_state(room))
        return json.loads(raw) if raw else {}

    async def set_state(self, r: Redis, room: str, **patch):
        """Оновлює стан сесії"""
        cur = await self.get_state(r, room)
        cur.update(patch)
        await r.set(self.k_state(room), json.dumps(cur))
        return cur

    async def start_question(self, r: Redis, room: str, qidx: int, duration_ms: int):
        """Запускає питання"""
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
        
        print(f"▶️ Запущено питання {qidx} на {duration_ms}ms")
        
        return {
            "type": "question_started",
            "questionIndex": qidx,
            "startedAt": now_ms,
            "durationMs": duration_ms,
            "question": question,
        }

    async def submit_answer(self, r: Redis, room: str, qidx: int, player_id: str, option_index: int) -> bool:
        """Зберігає відповідь гравця"""
        state = await self.get_state(r, room)
        
        # Перевірка фази
        if state.get("phase") != "QUESTION_ACTIVE":
            print(f"⚠️ Відповідь відхилена: питання неактивне (phase={state.get('phase')})")
            return False
        
        # Перевірка часу
        started = state.get("startedAt")
        dur = state.get("durationMs", 0)
        now_ms = int(time.time() * 1000)
        
        if started is None or now_ms > started + dur:
            print(f"⚠️ Відповідь відхилена: час вийшов")
            return False
        
        # зберігаємо першу відповідь гравця; повторні ігноруємо
        key = self.k_answers(room, qidx)
        exists = await r.hexists(key, player_id)
        
        if exists:
            print(f"⚠️ Відповідь відхилена: гравець вже відповідав")
            return False
        
        await r.hset(key, mapping={player_id: str(option_index)})
        await r.expire(key, 6 * 60 * 60)
        
        print(f"✅ Збережено відповідь: player={player_id[:8]}, option={option_index}")
        return True

    async def reveal_answer(self, r: Redis, room: str, qidx: int):
        """Розкриває правильну відповідь та рахує бали"""
        # рахуємо результати для питання
        questions = await self.load_questions(r, room)
        question = questions[qidx]
        correct_idx = int(question["correct_answer"])  # 0..3
        
        answers = await r.hgetall(self.k_answers(room, qidx))
        
        # оновлюємо скорборд
        correct_count = 0
        for player_id, opt in answers.items():
            if int(opt) == correct_idx:
                await r.zincrby(self.k_score(room), 100, player_id)  # +100 балів за правильну відповідь
                correct_count += 1
        
        await r.expire(self.k_score(room), 6 * 60 * 60)
        await self.set_state(r, room, phase="REVEAL")
        
        # агрегат для фронта
        counts = {"0": 0, "1": 0, "2": 0, "3": 0}
        for opt in answers.values():
            counts[str(opt)] = counts.get(str(opt), 0) + 1
        
        print(f"👁️ Розкрито відповідь {qidx}: правильна={correct_idx}, правильних відповідей={correct_count}/{len(answers)}")
        
        return {
            "type": "answer_revealed",
            "questionIndex": qidx,
            "correctIndex": correct_idx,
            "distribution": {int(k): v for k, v in counts.items()}
        }

    async def scoreboard(self, r: Redis, room: str) -> list[dict]:
        """Повертає таблицю лідерів"""
        # Отримуємо всіх гравців (навіть з 0 балами)
        all_players = await r.hgetall(self.k_players(room))
        
        # Отримуємо гравців з балами
        players_with_scores = await r.zrevrange(self.k_score(room), 0, -1, withscores=True)
        
        # Створюємо словник балів
        scores_dict = {pid: int(score) for pid, score in players_with_scores}
        
        # Формуємо результат для всіх гравців
        result = []
        for player_id, player_name in all_players.items():
            result.append({
                "playerId": player_id,
                "name": player_name,
                "score": scores_dict.get(player_id, 0)  # 0 якщо немає балів
            })
        
        # Сортуємо за балами (від більшого до меншого)
        result.sort(key=lambda x: x["score"], reverse=True)
        
        print(f"📊 Scoreboard для {room}: {len(result)} гравців")
        for p in result:
            print(f"   - {p['name']}: {p['score']} балів")
        
        return result