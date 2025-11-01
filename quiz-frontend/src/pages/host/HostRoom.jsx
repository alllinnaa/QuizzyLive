import { useEffect, useRef, useState } from "react";
import { createWS } from "../../realtime/wsClient";
import { gameState, applyEvent } from "../../realtime/store/gameStore";
import TimerBar from "../../components/TimerBar";
import { quizApi } from "../../api/quizApi";

export default function HostRoom() {
  const [roomCode, setRoomCode] = useState("ABCD12");
  const [duration, setDuration] = useState(20000);

  const [loadingQuizzes, setLoadingQuizzes] = useState(false);
  const [quizzes, setQuizzes] = useState([]);
  const [selectedQuizId, setSelectedQuizId] = useState("");
  const [selectedQuizTitle, setSelectedQuizTitle] = useState("");
  const [questions, setQuestions] = useState([]);

  const [wsStatus, setWsStatus] = useState("disconnected");
  const [lastError, setLastError] = useState("");

  const wsRef = useRef(null);
  const [, forceRender] = useState(0);

  const normalizeQuestions = (qs) =>
    (qs || [])
      .map((q, idx) => ({
        id: q.id ?? `q_${idx}`,
        question_text: q.question_text ?? q.questionText ?? "",
        answers: q.answers ?? q.options ?? [],
        correct_answer: q.correct_answer ?? q.correctAnswer ?? 0,
        position: q.position ?? idx,
      }))
      .sort((a, b) => (a.position ?? 0) - (b.position ?? 0));

  // 1) Список вікторин
  useEffect(() => {
    let ignore = false;
    (async () => {
      try {
        setLoadingQuizzes(true);
        const items = await quizApi.list();
        if (!ignore) setQuizzes(Array.isArray(items) ? items : []);
      } catch (e) {
        if (!ignore) setLastError("Не вдалося завантажити вікторини");
        console.error(e);
      } finally {
        if (!ignore) setLoadingQuizzes(false);
      }
    })();
    return () => { ignore = true; };
  }, []);

  // 2) WS-підключення
  useEffect(() => {
    setWsStatus("connecting");
    setLastError("");
    const ws = createWS({ role: "host", roomCode });
    wsRef.current = ws;

    ws.onopen = () => {
      setWsStatus("connected");
      gameState.connected = true;
      forceRender(x => x + 1);
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg?.type === "error") {
          setLastError(msg.message || "Помилка від сервера");
          return;
        }
        applyEvent(msg);
        forceRender(x => x + 1);
      } catch (err) {
        console.error("WS parse error", err);
      }
    };

    ws.onerror = () => console.warn("WS error (non-fatal)");
    ws.onclose  = () => {
      setWsStatus("disconnected");
      gameState.connected = false;
      forceRender(x => x + 1);
    };

    return () => ws.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roomCode]);

  // 3) Вибір вікторини → питання
  const onSelectQuiz = async (quizId) => {
    setSelectedQuizId(quizId);
    setSelectedQuizTitle(quizzes.find(q => q.id === quizId)?.title || "");
    setQuestions([]);
    setLastError("");
    if (!quizId) return;
    try {
      const quiz = await quizApi.getById(quizId); // { id, title, questions: [...] }
      setSelectedQuizTitle(quiz?.title || setSelectedQuizTitle);
      const qs = normalizeQuestions(quiz?.questions || []);
      setQuestions(qs);
    } catch (e) {
      setLastError("Не вдалося завантажити питання");
      console.error(e);
    }
  };

  // 4) Керування грою
  const createSession = () => {
    if (!questions.length) {
      setLastError("Оберіть вікторину та дочекайтесь завантаження питань");
      return;
    }
    setLastError("");
    wsRef.current?.send(JSON.stringify({ type: "host:create_session", roomCode, questions }));
  };

  const startQuestion = (questionIndex) => {
    if (questionIndex < 0 || questionIndex >= questions.length) return;
    setLastError("");
    wsRef.current?.send(JSON.stringify({ type: "host:start_question", questionIndex, durationMs: duration }));
  };

  const reveal = () => {
    if (gameState.questionIndex < 0) return;
    setLastError("");
    wsRef.current?.send(JSON.stringify({ type: "host:reveal_answer", questionIndex: gameState.questionIndex }));
  };

  const endSession = () => {
    setLastError("");
    wsRef.current?.send(JSON.stringify({ type: "host:end_session" }));
  };

  const isCorrect = (i) => gameState.reveal?.correctIndex === i;

  return (
    <div style={{ maxWidth: 1000, margin: "24px auto", padding: 16 }}>
      <h1>Host Panel</h1>

      <div style={{ marginBottom: 12 }}>
        <div>WS: <strong>{wsStatus}</strong></div>
        {lastError && <div style={{ color: "#b91c1c" }}>{lastError}</div>}
        <div>Phase: <strong>{gameState.phase}</strong></div>
        <div>Current question index: <strong>{gameState.questionIndex}</strong></div>
      </div>

      {/* Інформація про обрану вікторину */}
      <div style={{ border: "1px solid #eee", padding: 12, borderRadius: 8, marginBottom: 12 }}>
        <div><strong>Кімната:</strong> {roomCode}</div>
        <div><strong>Вікторина:</strong> {selectedQuizTitle || "не обрано"}</div>
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", marginBottom: 16 }}>
        <label>
          Room:&nbsp;
          <input value={roomCode} onChange={(e) => setRoomCode(e.target.value)} style={{ width: 140 }} />
        </label>

        <label>
          Вікторина:&nbsp;
          <select disabled={loadingQuizzes} value={selectedQuizId} onChange={(e) => onSelectQuiz(e.target.value)}>
            <option value="">— оберіть —</option>
            {quizzes.map((q) => <option key={q.id} value={q.id}>{q.title}</option>)}
          </select>
        </label>

        <button onClick={createSession} disabled={!questions.length || wsStatus !== "connected"}>
          Create session
        </button>

        <label>
          Time (ms):&nbsp;
          <input
            type="number"
            value={duration}
            onChange={(e) => setDuration(parseInt(e.target.value || "0", 10))}
            style={{ width: 120 }}
          />
        </label>

        <button onClick={reveal} disabled={wsStatus !== "connected"}>Reveal</button>
        <button onClick={endSession} disabled={wsStatus !== "connected"}>End session</button>
      </div>

      {/* Поточне питання з підсвіткою правильної відповіді під час REVEAL */}
      {gameState.question && (
        <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12, marginBottom: 20 }}>
          <h3>Питання {gameState.questionIndex + 1}</h3>
          <p>{gameState.question.question_text}</p>
          <ol>
            {gameState.question.answers.map((a, i) => {
              const correct = isCorrect(i);
              const style = {
                background: gameState.phase === "REVEAL" ? (correct ? "#16a34a22" : "#f9fafb") : "#f9fafb",
                borderRadius: 6, padding: "4px 8px", margin: "2px 0"
              };
              return <li key={i} style={style}>{a}</li>;
            })}
          </ol>
          <TimerBar startedAt={gameState.startedAt} durationMs={gameState.durationMs} />
        </div>
      )}

      <h2>Питання вікторини</h2>
      {!questions.length && <p>Оберіть вікторину — з’явиться список питань.</p>}
      <ul>
        {questions.map((q, i) => (
          <li key={q.id} style={{ marginBottom: 6 }}>
            <button
              onClick={() => startQuestion(i)}
              disabled={wsStatus !== "connected"}
              style={{ marginRight: 8 }}
            >
              Показати
            </button>
            #{i + 1}: {q.question_text}
          </li>
        ))}
      </ul>

      <h2>Scoreboard</h2>
      <ul>
        {gameState.scoreboard.map((r) => (<li key={r.playerId}>{r.name}: {r.score}</li>))}
      </ul>
    </div>
  );
}
