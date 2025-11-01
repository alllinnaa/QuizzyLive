from typing import List, Optional
from .typing import to_iso
from ..repositories.quiz_repository import QuizRepository

class QuizService:
    def __init__(self, repo: QuizRepository) -> None:
        self.repo = repo

    def list_quizzes(self) -> list[dict]:
        items = self.repo.list_quizzes()
        return [
            {
                "id": i["id"],
                "title": i["title"],
                "updatedAt": to_iso(i["updated_at"]),
            }
            for i in items
        ]

    def get_quiz(self, quiz_id: str) -> Optional[dict]:
        res = self.repo.get_quiz_with_questions(quiz_id)
        if not res:
            return None
        quiz, questions = res
        return {
            "id": quiz["id"],
            "title": quiz["title"],
            "createdAt": to_iso(quiz["created_at"]),
            "updatedAt": to_iso(quiz["updated_at"]),
            "questions": [
                {
                    "id": q["id"],
                    "questionText": q["question_text"],
                    "answers": q["answers"],
                    "correctAnswer": q["correct_answer"],
                    "position": q["position"],
                }
                for q in questions
            ],
        }

    def create_quiz(self, title: str, questions: List[dict]) -> str:
        return self.repo.create_quiz(title, questions)

    def update_quiz(self, quiz_id: str, title: Optional[str], questions: Optional[List[dict]]) -> None:
        self.repo.update_quiz(quiz_id, title, questions)

    def delete_quiz(self, quiz_id: str) -> None:
        self.repo.delete_quiz(quiz_id)