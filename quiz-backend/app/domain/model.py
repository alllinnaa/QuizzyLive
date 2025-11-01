from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class Question:
    question_text: str
    answers: list[str]
    correct_answer: int
    position: int

@dataclass(frozen=True)
class Quiz:
    id: str
    title: str
    questions: List[Question]