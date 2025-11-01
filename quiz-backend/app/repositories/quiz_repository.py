from typing import List, Optional, Tuple
from supabase import Client

class QuizRepository:
    def __init__(self, client: Client) -> None:
        self.client = client

    def list_quizzes(self) -> List[dict]:
        res = (
            self.client.table("quizzes")
            .select("id,title,updated_at")
            .order("updated_at", desc=True)
            .execute()
        )
        return res.data or []

    def get_quiz_with_questions(self, quiz_id: str) -> Optional[Tuple[dict, List[dict]]]:
        quiz_res = (
            self.client.table("quizzes")
            .select("*")
            .eq("id", quiz_id)
            .single()
            .execute()
        )
        if not quiz_res.data:
            return None

        q_res = (
            self.client.table("questions")
            .select("*")
            .eq("quiz_id", quiz_id)
            .order("position", desc=False)
            .execute()
        )
        return quiz_res.data, (q_res.data or [])

    def create_quiz(self, title: str, questions: List[dict]) -> str:
        # ⬇️ ВАЖЛИВО: без .select()/.single() після insert
        quiz_ins = self.client.table("quizzes").insert({"title": title}).execute()

        # supabase-py v2 зазвичай повертає representation у data (список рядків)
        if not quiz_ins.data or not isinstance(quiz_ins.data, list) or "id" not in quiz_ins.data[0]:
            # fallback: ще раз прочитати щойно створений запис (малоймовірно знадобиться)
            # але краще одразу підняти явну помилку:
            raise RuntimeError("Insert quizzes failed: no returned id")

        quiz_id = quiz_ins.data[0]["id"]

        # масове додавання питань
        rows = []
        for idx, q in enumerate(questions):
            rows.append(
                {
                    "quiz_id": quiz_id,
                    "question_text": q["questionText"],
                    "answers": q["answers"],
                    "correct_answer": q["correctAnswer"],
                    "position": idx,
                }
            )
        if rows:
            self.client.table("questions").insert(rows).execute()

        return quiz_id

    def update_quiz(self, quiz_id: str, title: Optional[str], questions: Optional[List[dict]]) -> None:
        if title is not None:
            # ⬇️ просто .execute(), без .select()
            self.client.table("quizzes").update({"title": title}).eq("id", quiz_id).execute()

        if questions is not None:
            # Проста стратегія: видалити всі питання та вставити нові
            self.client.table("questions").delete().eq("quiz_id", quiz_id).execute()
            rows = []
            for idx, q in enumerate(questions):
                rows.append(
                    {
                        "quiz_id": quiz_id,
                        "question_text": q["questionText"],
                        "answers": q["answers"],
                        "correct_answer": q["correctAnswer"],
                        "position": idx,
                    }
                )
            if rows:
                self.client.table("questions").insert(rows).execute()

    def delete_quiz(self, quiz_id: str) -> None:
        self.client.table("quizzes").delete().eq("id", quiz_id).execute()