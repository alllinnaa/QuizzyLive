from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class AnswerOption(BaseModel):
    text: str


class Question(BaseModel):
    id: str | int
    question_text: str
    answers: list[str]
    correct_answer: int
    position: int


class HostCreateSession(BaseModel):
    type: Literal["host:create_session"] = "host:create_session"
    roomCode: str
    quizId: Optional[str] = None
    questions: List[Question]


class HostStartQuestion(BaseModel):
    type: Literal["host:start_question"] = "host:start_question"
    questionIndex: int
    durationMs: int


class HostRevealAnswer(BaseModel):
    type: Literal["host:reveal_answer"] = "host:reveal_answer"
    questionIndex: Optional[int] = None


class HostNextQuestion(BaseModel):
    type: Literal["host:next_question"] = "host:next_question"
    questionIndex: Optional[int] = None
    durationMs: int = 30000


class HostEndSession(BaseModel):
    type: Literal["host:end_session"] = "host:end_session"


class PlayerJoin(BaseModel):
    type: Literal["player:join"] = "player:join"
    name: str
    roomCode: Optional[str] = None


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
    question: dict | None = None
    scoreboard: list[dict] | None = None
    reveal: dict | None = None
    # нове поле — ідентифікатор поточного гравця
    playerId: str | None = None


class FinishedSessionSnapshot(BaseModel):
    type: Literal["finished_session"] = "finished_session"
    sessionId: str
    roomCode: str
    quizId: str | None = None
    createdAt: int
    endedAt: int
    questions: list[dict]
    scoreboard: list[dict]


EventPayload = (
    HostCreateSession
    | HostStartQuestion
    | HostRevealAnswer
    | HostNextQuestion
    | HostEndSession
    | PlayerJoin
    | PlayerAnswer
)

#    Поки не використовуємо, а лише як тип DTO
#    HostStartQuestion,
#    HostRevealAnswer,
#    HostNextQuestion,
#    HostEndSession,