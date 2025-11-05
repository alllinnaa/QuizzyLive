import json
import time
import asyncio
from typing import Dict, Set, Optional

from fastapi.websockets import WebSocket
from redis.asyncio import Redis

REDIS_PREFIX = "quiz:room:"


class RoomManager:
    def __init__(self) -> None:
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

    async def register(self, room: str, ws: WebSocket) -> None:
        """Реєструє WebSocket з'єднання в кімнаті"""
        await ws.accept()
        self.connections.setdefault(room, set()).add(ws)
        print(
            f"Зареєстровано з'єднання в кімнаті {room}. "
            f"Всього: {len(self.connections[room])}"
        )

    async def unregister(self, room: str, ws: WebSocket) -> None:
        """Видаляє WebSocket з'єднання з кімнати"""
        try:
            if room in self.connections:
                self.connections[room].discard(ws)
                print(
                    f"Видалено з'єднання з кімнати {room}. "
                    f"Залишилось: {len(self.connections[room])}"
                )
                # Видаляємо кімнату якщо порожня
                if not self.connections[room]:
                    del self.connections[room]
                    print(f"Кімната {room} видалена (немає з'єднань)")
        except Exception as e:
            print(f" Помилка при видаленні з'єднання: {str(e)}")

    async def broadcast(
        self,
        room: str,
        message: dict,
        exclude: Optional[WebSocket] = None,
    ) -> None:
        """
        Розсилає повідомлення всім підключеним до кімнати.

        Args:
            room: Код кімнати
            message: Повідомлення
            exclude: WebSocket який треба виключити з розсилки (опціонально)
        """
        if room not in self.connections:
            print(f"Кімната {room} не існує для broadcast")
            return

        connections = self.connections[room]
        message_type = message.get("type", "unknown")
        print(f"Broadcast до {room}: {message_type} ({len(connections)} з'єднань)")

        data = json.dumps(message)
        disconnected: list[WebSocket] = []
        sent_count = 0

        for ws in list(connections):
            # Пропускаємо виключений WebSocket
            if exclude is not None and ws == exclude:
                print("Пропускаємо excluded websocket")
                continue
            try:
                await ws.send_text(data)
                sent_count += 1
            except Exception as e:
                print(f" Помилка відправки: {str(e)}")
                disconnected.append(ws)

        print(f" Надіслано {sent_count} з {len(connections)} з'єднань")

        # Видаляємо відключені з'єднання
        for ws in disconnected:
            await self.unregister(room, ws)

    # --- стан сесії ---

    async def create_session(
        self,
        r: Redis,
        room: str,
        questions: list[dict],
        session_id: str,
        created_at_ms: int,
    ) -> None:
        """Створює нову сесію вікторини"""
        # зберігаємо список питань один раз
        await r.set(self.k_questions(room), json.dumps(questions))

        # початковий стан
        state = {
            "phase": "LOBBY",
            "questionIndex": -1,
            "startedAt": None,
            "durationMs": None,
            "sessionId": session_id,
            "createdAt": created_at_ms,
        }
        await r.set(self.k_state(room), json.dumps(state))

        # скидаємо службові структури
        await r.delete(self.k_score(room))

        # TTL на кімнату: 6 годин
        await r.expire(self.k_questions(room), 6 * 60 * 60)
        await r.expire(self.k_state(room), 6 * 60 * 60)

        print(
            f"Створено сесію для кімнати {room} з {len(questions)} питаннями "
            f"(sessionId={session_id})"
        )

    async def load_questions(self, r: Redis, room: str) -> list[dict]:
        """Завантажує питання сесії з Redis"""
        raw = await r.get(self.k_questions(room))
        return json.loads(raw) if raw else []

    async def get_state(self, r: Redis, room: str) -> dict:
        """Отримує поточний стан сесії"""
        raw = await r.get(self.k_state(room))
        return json.loads(raw) if raw else {}

    async def set_state(self, r: Redis, room: str, **patch: object) -> dict:
        """Оновлює стан сесії"""
        cur = await self.get_state(r, room)
        cur.update(patch)
        await r.set(self.k_state(room), json.dumps(cur))
        return cur

    async def _auto_reveal_after_timeout(
        self,
        r: Redis,
        room: str,
        qidx: int,
        duration_ms: int,
    ) -> None:
        """
        Внутрішній таймер: після закінчення часу питання
        автоматично розкриває відповідь, якщо хост цього ще не зробив.
        """
        try:
            # чекаємо тривалість питання
            await asyncio.sleep(duration_ms / 1000.0)

            state = await self.get_state(r, room)
            current_phase = state.get("phase")
            current_qidx = state.get("questionIndex")

            # якщо фаза змінилась або питання інше — нічого не робимо
            if current_phase != "QUESTION_ACTIVE":
                print(
                    f"[auto_reveal] Пропуск: phase={current_phase} "
                    f"для кімнати {room}, qidx={current_qidx}"
                )
                return

            if current_qidx != qidx:
                print(
                    f"[auto_reveal] Пропуск: поточне питання {current_qidx}, "
                    f"очікувалось {qidx} для кімнати {room}"
                )
                return

            print(
                f"[auto_reveal] Автоматичне розкриття відповіді для кімнати "
                f"{room}, питання {qidx}"
            )

            msg = await self.reveal_answer(r, room, qidx)
            sb = await self.scoreboard(r, room)
            msg["scoreboard"] = sb

            await self.broadcast(room, msg)

        except Exception as e:
            print(f"[auto_reveal] Помилка: {e}")

    async def start_question(
        self,
        r: Redis,
        room: str,
        qidx: int,
        duration_ms: int,
    ) -> dict:
        """
        Запускає питання, оновлює стан, очищає відповіді
        і планує авто-показ правильної відповіді після закінчення таймера.
        """
        now_ms = int(time.time() * 1000)

        await self.set_state(
            r,
            room,
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

        print(f"Запущено питання {qidx} на {duration_ms}ms")

        # плануємо авто-розкриття відповіді
        asyncio.create_task(
            self._auto_reveal_after_timeout(r, room, qidx, duration_ms)
        )

        return {
            "type": "question_started",
            "questionIndex": qidx,
            "startedAt": now_ms,
            "durationMs": duration_ms,
            "question": question,
        }

    async def submit_answer(
        self,
        r: Redis,
        room: str,
        qidx: int,
        player_id: str,
        option_index: int,
    ) -> bool:
        """Зберігає відповідь гравця"""
        state = await self.get_state(r, room)

        # Перевірка фази
        if state.get("phase") != "QUESTION_ACTIVE":
            print(
                f"Відповідь відхилена: питання неактивне "
                f"(phase={state.get('phase')})"
            )
            return False

        # Перевірка часу
        started = state.get("startedAt")
        dur = state.get("durationMs", 0)
        now_ms = int(time.time() * 1000)

        if started is None or now_ms > started + dur:
            print("Відповідь відхилена: час вийшов")
            return False

        # зберігаємо першу відповідь гравця; повторні ігноруємо
        key = self.k_answers(room, qidx)
        exists = await r.hexists(key, player_id)
        if exists:
            print("Відповідь відхилена: гравець вже відповідав")
            return False

        await r.hset(key, mapping={player_id: str(option_index)})
        await r.expire(key, 6 * 60 * 60)

        print(f"Збережено відповідь: player={player_id[:8]}, option={option_index}")

        return True

    async def reveal_answer(self, r: Redis, room: str, qidx: int) -> dict:
        """Розкриває правильну відповідь та рахує бали"""
        # рахуємо результати для питання
        questions = await self.load_questions(r, room)
        question = questions[qidx]
        correct_idx = int(question["correct_answer"])

        answers = await r.hgetall(self.k_answers(room, qidx))

        # оновлюємо скорборд
        correct_count = 0
        for player_id, opt in answers.items():
            if int(opt) == correct_idx:
                await r.zincrby(self.k_score(room), 100, player_id)
                correct_count += 1

        await r.expire(self.k_score(room), 6 * 60 * 60)
        await self.set_state(r, room, phase="REVEAL")

        # агрегат для фронта
        counts: dict[str, int] = {"0": 0, "1": 0, "2": 0, "3": 0}
        for opt in answers.values():
            key = str(opt)
            counts[key] = counts.get(key, 0) + 1

        print(
            f"Розкрито відповідь {qidx}: правильна={correct_idx}, "
            f"правильних відповідей={correct_count}/{len(answers)}"
        )

        return {
            "type": "answer_revealed",
            "questionIndex": qidx,
            "correctIndex": correct_idx,
            "distribution": {int(k): v for k, v in counts.items()},
        }

    async def scoreboard(self, r: Redis, room: str) -> list[dict]:
        """Повертає таблицю лідерів"""
        # Отримуємо всіх гравців (навіть з 0 балами)
        all_players = await r.hgetall(self.k_players(room))

        # Отримуємо гравців з балами
        players_with_scores = await r.zrevrange(
            self.k_score(room),
            0,
            -1,
            withscores=True,
        )

        # Створюємо словник балів
        scores_dict = {pid: int(score) for pid, score in players_with_scores}

        # Формуємо результат для всіх гравців
        result: list[dict] = []
        for player_id, player_name in all_players.items():
            result.append(
                {
                    "playerId": player_id,
                    "name": player_name,
                    "score": scores_dict.get(player_id, 0),
                }
            )

        # Сортуємо за балами (від більшого до меншого)
        result.sort(key=lambda x: x["score"], reverse=True)

        print(f"Scoreboard для {room}: {len(result)} гравців")
        for p in result:
            print(f" - {p['name']}: {p['score']} балів")

        return result

    async def cleanup_room_data(self, r: Redis, room: str) -> None:
        """Очищує службові дані кімнати після завершення вікторини"""
        await r.delete(self.k_state(room))
        await r.delete(self.k_questions(room))
        await r.delete(self.k_score(room))
        await r.delete(self.k_players(room))
