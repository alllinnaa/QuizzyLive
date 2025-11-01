// quiz-frontend/src/store/gameStore.js
export const gameState = {
  roomCode: "",
  role: "player",
  connected: false,
  phase: "LOBBY",
  questionIndex: -1,
  startedAt: null,
  durationMs: null,
  question: null,
  scoreboard: [],
  reveal: null,
  myAnswer: null,
  playerId: null, // NEW: ідентифікатор гравця з join_ok
};

export function applyEvent(evt) {
  switch (evt.type) {
    case "state_sync":
      Object.assign(gameState, {
        phase: evt.phase,
        questionIndex: evt.questionIndex,
        startedAt: evt.startedAt ?? null,
        durationMs: evt.durationMs ?? null,
        question: evt.question ?? null,
        scoreboard: evt.scoreboard ?? [],
        reveal: evt.reveal ?? null,
        // myAnswer і playerId не змінюємо тут
      });
      break;

    case "question_started":
      Object.assign(gameState, {
        phase: "QUESTION_ACTIVE",
        questionIndex: evt.questionIndex,
        startedAt: evt.startedAt,
        durationMs: evt.durationMs,
        question: evt.question,
        reveal: null,
        myAnswer: null, // важливо: скидання при новому питанні
      });
      break;

    case "answer_revealed":
      Object.assign(gameState, {
        phase: "REVEAL",
        reveal: { correctIndex: evt.correctIndex, distribution: evt.distribution },
        scoreboard: evt.scoreboard || gameState.scoreboard,
      });
      break;

    case "next_question_ready":
      Object.assign(gameState, {
        phase: "LOBBY",
        reveal: null,
        question: null,
        startedAt: null,
        durationMs: null,
      });
      break;

    case "session_ended":
      Object.assign(gameState, { phase: "ENDED", scoreboard: evt.scoreboard || [] });
      break;

    default:
      break;
  }
}
