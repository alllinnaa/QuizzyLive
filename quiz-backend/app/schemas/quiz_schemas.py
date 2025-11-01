from typing import Annotated, List, Optional
from pydantic import BaseModel, Field, conlist, field_validator

class QuestionIn(BaseModel):
    questionText: str = Field(..., min_length=1)
    answers: Annotated[list[str], Field(min_length=4, max_length=4)]  # рівно 4
    correctAnswer: int = Field(..., ge=0, le=3)

class QuizCreateIn(BaseModel):
    title: str = Field(..., min_length=1)
    questions: List[QuestionIn]

class QuizUpdateIn(BaseModel):
    title: Optional[str] = Field(None, min_length=1)
    questions: Optional[List[QuestionIn]] = None

    @field_validator("questions")
    @classmethod
    def validate_questions(cls, v):
        return v

class QuestionOut(BaseModel):
    id: str
    questionText: str
    answers: list[str]
    correctAnswer: int
    position: int

class QuizOut(BaseModel):
    id: str
    title: str
    questions: List[QuestionOut]
    createdAt: str
    updatedAt: str

class QuizListItem(BaseModel):
    id: str
    title: str
    updatedAt: str