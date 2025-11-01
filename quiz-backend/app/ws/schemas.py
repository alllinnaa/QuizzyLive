from pydantic import BaseModel, Field
from typing import List, Literal, Optional

class AnswerOption(BaseModel):
    text: str

class Question(BaseModel):
    id: str
    question_text: str
    answers: list[str]
    correct_answer: int
    position: int

class HostCreateSession(BaseModel):
    type: Literal["host:create_session"] = "host:create_session"
    roomCode: str = Field(min_length=4, max_length=16)
    quizId: Optional[str] = None  # опційно, якщо потрібно логувати в БД
    questions: List[Question]

class HostStartQuestion(BaseModel):
    type: Literal["host:start_question"] = "host:start_question"
    questionIndex: int
    durationMs: int

class HostRevealAnswer(BaseModel):
    type: Literal["host:reveal_answer"] = "host:reveal_answer"
    questionIndex: int

class HostNextQuestion(BaseModel):
    type: Literal["host:next_question"] = "host:next_question"
    questionIndex: int

class HostEndSession(BaseModel):
    type: Literal["host:end_session"] = "host:end_session"

class PlayerJoin(BaseModel):
    type: Literal["player:join"] = "player:join"
    name: str

class PlayerAnswer(BaseModel):
    type: Literal["player:answer"] = "player:answer"
    questionIndex: int
    optionIndex: int

class ServerStateSync(BaseModel):
    type: Literal["state_sync"] = "state_sync"
    roomCode: str
    phase: Literal["LOBBY", "QUESTION_ACTIVE", "REVEAL", "ENDED"]
    questionIndex: int
    startedAt: int | None = None
    durationMs: int | None = None
    question: Question | None = None
    scoreboard: list[dict] | None = None
    reveal: dict | None = None

# допоміжна
EventPayload = (
    HostCreateSession | HostStartQuestion | HostRevealAnswer |
    HostNextQuestion | HostEndSession | PlayerJoin | PlayerAnswer
)