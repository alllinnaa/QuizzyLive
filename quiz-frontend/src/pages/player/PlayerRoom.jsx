import { useEffect, useRef, useState } from "react";
import { createWS } from "../../realtime/wsClient.js";
import { gameState, applyEvent } from "../../realtime/store/gameStore.js";
import TimerBar from "../../components/TimerBar";

export default function PlayerRoom() {
  const [roomCode, setRoomCode] = useState("ABCD12");
  const [name,   setName]   = useState("Player");

  const [wsStatus, setWsStatus] = useState("disconnected"); // disconnected | connecting | connected
  const [lastError, setLastError] = useState("");

  const wsRef = useRef(null);
  const [, forceRender] = useState(0);

  useEffect(() => () => wsRef.current?.close(), []);

  const join = () => {
    setLastError("");
    setWsStatus("connecting");
    const ws = createWS({ role: "player", roomCode, name });
    wsRef.current = ws;

    ws.onopen = () => {
      // Явна реєстрація гравця — критично для коректної ідентифікації на бекенді
      ws.send(JSON.stringify({ type: "player:join", name }));
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
  };

  const answer = (idx) => {
    if (gameState.phase !== "QUESTION_ACTIVE") return;
    if (gameState.myAnswer !== null) return; // не даємо кліками змінювати першу відповідь
    wsRef.current?.send(JSON.stringify({
      type: "player:answer",
      questionIndex: gameState.questionIndex,
      optionIndex: idx,
    }));
    // локальна відмітка: одразу підсвічуємо наш вибір (навіть до reveal)
    gameState.myAnswer = idx;
    forceRender(x => x + 1);
  };

  const isCorrect = (i) => gameState.reveal?.correctIndex === i;

  const Waiting = () => (
    <div style={{ border: "1px dashed #aaa", padding: 16, borderRadius: 8 }}>
      Очікуйте, поки хост покаже перше питання…
    </div>
  );

  return (
    <div style={{ maxWidth: 800, margin: "24px auto", padding: 16 }}>
      <h1>Player</h1>

      <div style={{ marginBottom: 12 }}>
        <div>WS: <strong>{wsStatus}</strong></div>
        {lastError && <div style={{ color: "#b91c1c" }}>{lastError}</div>}
        <div>Phase: <strong>{gameState.phase}</strong></div>
      </div>

      {wsStatus !== "connected" && (
        <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
          <input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
          <input placeholder="Room" value={roomCode} onChange={(e) => setRoomCode(e.target.value)} />
          <button onClick={join}>Join</button>
        </div>
      )}

      {wsStatus === "connected" && !gameState.question && <Waiting />}

      {wsStatus === "connected" && gameState.question && (
        <div style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12, marginBottom: 12 }}>
          <h3>Питання {gameState.questionIndex + 1}</h3>
          <p>{gameState.question.question_text}</p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {gameState.question.answers.map((a, i) => {
              // Візуальні стани:
              const chosen = gameState.myAnswer === i;
              const correct = isCorrect(i);
              const chosenWrong = gameState.reveal && chosen && !correct;

              const style = {
                padding: 12,
                border: "1px solid #ccc",
                borderRadius: 8,
                background:
                  gameState.reveal
                    ? (correct ? "#16a34a22" : (chosenWrong ? "#dc262622" : "#f9fafb"))
                    : (chosen ? "#e5e7eb" : "#f9fafb"),
                cursor: (gameState.phase === "QUESTION_ACTIVE" && gameState.myAnswer === null) ? "pointer" : "default",
                opacity: (gameState.phase === "QUESTION_ACTIVE" && gameState.myAnswer !== null && !chosen) ? 0.7 : 1,
              };

              const disabled = gameState.phase !== "QUESTION_ACTIVE" || gameState.myAnswer !== null;

              return (
                <button key={i} onClick={() => answer(i)} style={style} disabled={disabled}>
                  {a}
                </button>
              );
            })}
          </div>

          <div style={{ marginTop: 12 }}>
            <TimerBar startedAt={gameState.startedAt} durationMs={gameState.durationMs} />
          </div>
        </div>
      )}

      {wsStatus === "connected" && gameState.phase === "REVEAL" && (
        <div style={{ marginTop: 12 }}>
          <strong>Правильна відповідь показана. Очікуйте наступного питання.</strong>
        </div>
      )}

      {wsStatus === "connected" && gameState.phase === "ENDED" && (
        <div style={{ marginTop: 12 }}>
          <h2>Фінальний рахунок</h2>
          <ul>
            {gameState.scoreboard.map(r => (<li key={r.playerId}>{r.name}: {r.score}</li>))}
          </ul>
        </div>
      )}
    </div>
  );
}