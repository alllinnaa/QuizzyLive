import React, { useEffect, useState, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { createQuizSocket } from "../../api/wsClient";
import "./QuizPlayPage.css";

function QuizPlayPage() {
  const navigate = useNavigate();
  const { quizId } = useParams();

  const [ws, setWs] = useState(null);
  const [question, setQuestion] = useState(null);
  const [remaining, setRemaining] = useState(0);
  const [selected, setSelected] = useState(null);
  const [phase, setPhase] = useState("CONNECTING");
  const [correctAnswer, setCorrectAnswer] = useState(null);
  const [playerName, setPlayerName] = useState("");
  const [connectionStatus, setConnectionStatus] = useState("connecting");
  const [timeUp, setTimeUp] = useState(false);

  const timerRef = useRef(null);
  const wsInitialized = useRef(false);

  useEffect(() => {
    if (wsInitialized.current) return;
    wsInitialized.current = true;

    const name = localStorage.getItem("playerName") || "Player";
    setPlayerName(name);

    console.log("Підключення учасника:", { name, quizId });

    const socket = createQuizSocket({
      role: "player",
      roomCode: quizId,
      name: name,
      onMessage: (msg) => {
        console.log("Player отримав:", msg);

        switch (msg.type) {
          case "state_sync": {
            console.log("State sync:", msg.phase);
            setPhase(msg.phase || "WAITING");
            setConnectionStatus("connected");
            break;
          }

          case "player_joined": {
            console.log("Успішно приєдналися до вікторини!");
            setConnectionStatus("connected");
            setPhase("WAITING");
            break;
          }

          case "question_started": {
            console.log("Почалось питання:", msg.question);
            setQuestion(msg.question);
            setRemaining(Math.floor(msg.durationMs / 1000));
            setPhase("QUESTION_ACTIVE");
            setSelected(null);
            setCorrectAnswer(null);
            setTimeUp(false);

            if (timerRef.current) {
              clearInterval(timerRef.current);
            }

            timerRef.current = setInterval(() => {
              setRemaining((prev) => {
                if (prev <= 1) {
                  clearInterval(timerRef.current);
                  setTimeUp(true);
                  return 0;
                }
                return prev - 1;
              });
            }, 1000);

            break;
          }

          case "answer_revealed": {
            console.log("Показано відповідь:", msg.correctIndex);
            setPhase("REVEAL");
            setCorrectAnswer(msg.correctIndex);
            if (timerRef.current) {
              clearInterval(timerRef.current);
            }
            break;
          }

          case "session_ended":
          case "quiz_ended": {
            if (timerRef.current) {
              clearInterval(timerRef.current);
            }
            alert("Вікторина завершена!");
            navigate("/");
            break;
          }

          case "error": {
            console.error("Помилка від сервера:", msg.message);
            alert(`Помилка: ${msg.message}`);
            setConnectionStatus("error");
            if (
              msg.message?.includes("not found") ||
              msg.message?.includes("does not exist")
            ) {
              setTimeout(() => navigate("/join"), 2000);
            }
            break;
          }

          default: {
            console.log("Невідомий тип повідомлення:", msg.type);
          }
        }
      },
    });

    socket.onopen = () => {
      console.log("WebSocket підключено як player");
      setConnectionStatus("connected");
    };

    socket.onclose = (event) => {
      console.log("WebSocket закрито:", event);
      setConnectionStatus("disconnected");
      wsInitialized.current = false;
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };

    socket.onerror = (error) => {
      console.error("WebSocket помилка:", error);
      setConnectionStatus("error");
    };

    setWs(socket);

    return () => {
      console.log("Очищення WebSocket з'єднання");
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      if (socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
      wsInitialized.current = false;
    };
  }, [quizId, navigate]);

  const handleAnswer = (idx) => {
    // 🔒 Блок: якщо час вийшов або питання вже не активне — нічого не робимо
    if (timeUp || remaining <= 0) {
      console.log("Час вийшов, відповідь не приймається");
      return;
    }

    if (selected !== null || phase !== "QUESTION_ACTIVE") {
      console.log("Відповідь вже надіслана або питання неактивне");
      return;
    }

    console.log("Надсилаємо відповідь:", idx);
    setSelected(idx);

    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.sendJson({
        type: "player:answer",
        questionIndex: question.position,
        optionIndex: idx,
      });
    } else {
      console.error("WebSocket не підключено!");
    }
  };

  // 🔹 СТАН: підключення
  if (connectionStatus === "connecting" || phase === "CONNECTING") {
    return (
      <div className="quiz-play-page">
        <div className="status-box">
          <h2>Підключення до вікторини...</h2>
          <p>Код: {quizId}</p>
          <p>Ім&apos;я: {playerName}</p>
        </div>
      </div>
    );
  }

  // 🔹 СТАН: помилка
  if (connectionStatus === "error") {
    return (
      <div className="quiz-play-page">
        <div className="status-box error">
          <h2>Помилка підключення</h2>
          <p>Не вдалося підключитися до вікторини.</p>
          <p>Перевірте код вікторини та спробуйте ще раз.</p>
          <button onClick={() => navigate("/join")}>Повернутись</button>
        </div>
      </div>
    );
  }

  // 🔹 СТАН: відключено
  if (connectionStatus === "disconnected") {
    return (
      <div className="quiz-play-page">
        <div className="status-box">
          <h2>З&apos;єднання втрачено</h2>
          <p>Зв&apos;язок з сервером перервано.</p>
          <button onClick={() => window.location.reload()}>
            Перепідключитись
          </button>
          <button onClick={() => navigate("/join")}>Повернутись</button>
        </div>
      </div>
    );
  }

  // 🔹 Основний екран
  const isUrgent = remaining <= 5 && remaining > 0;

  return (
    <div className="quiz-play-page">
      {/* Заголовок гравця */}
      <header className="player-header">
        <span className="player-name">{playerName}</span>
        <span className="connection-status">
          {connectionStatus === "connected" ? "Підключено" : "Відключено"}
        </span>
      </header>

      {/* Очікування старту / наступного питання */}
      {phase === "WAITING" && (
        <div className="waiting-box">
          <h2>Очікуємо початку вікторини...</h2>
          <p>Ведучий почне гру незабаром.</p>
          <div className="pulse-indicator">●</div>
        </div>
      )}

      {/* Активне питання */}
      {phase === "QUESTION_ACTIVE" && question && (
        <div className="question-box">
          <div className="question-header">
            <h3>Питання {question.position + 1}</h3>
            <span className={`timer ${isUrgent ? "urgent" : ""}`}>
              {remaining} с
            </span>
          </div>

          <div className="question-text">{question.question_text}</div>

          <div className="answers-grid">
            {question.answers.map((ans, i) => (
              <button
                key={i}
                type="button"
                onClick={() => handleAnswer(i)}
                disabled={selected !== null || timeUp || remaining <= 0}
                className={`answer-btn ${
                  selected === i ? "selected" : ""
                }`}
              >
                <span className="answer-number">{i + 1}</span>
                <span className="answer-text">{ans}</span>
              </button>
            ))}
          </div>

          {selected !== null && !timeUp && (
            <div className="answer-submitted">Відповідь надіслано!</div>
          )}

          {timeUp && selected === null && (
            <div className="answer-submitted time-up-message">
              Час вийшов. Відповідь не була надіслана.
            </div>
          )}
        </div>
      )}

      {/* Показ результатів */}
      {phase === "REVEAL" && question && (
        <div className="reveal-box">
          <h2>Результати</h2>
          <p className="question-text">{question.question_text}</p>

          {question.answers.map((ans, i) => {
            const isCorrect = i === correctAnswer;
            const isSelected = i === selected;

            const classes = [
              "answer-result",
              isCorrect ? "correct" : "",
              isSelected ? "selected" : "",
            ]
              .filter(Boolean)
              .join(" ");

            return (
              <div key={i} className={classes}>
                <span className="answer-number">{i + 1}</span>
                <span className="answer-text">{ans}</span>
                {isCorrect && <span className="check">✓</span>}
                {isSelected && !isCorrect && <span className="cross">✗</span>}
              </div>
            );
          })}

          {selected === correctAnswer && selected !== null && (
            <div className="result-message success">
              Правильно! +100 балів
            </div>
          )}

          {selected !== correctAnswer && selected !== null && (
            <div className="result-message wrong">
              Неправильно. Правильна відповідь: {correctAnswer + 1}
            </div>
          )}

          {selected === null && (
            <div className="result-message missed">Час вийшов!</div>
          )}

          <div className="waiting-next">Очікуємо наступного питання...</div>
        </div>
      )}
    </div>
  );
}

export default QuizPlayPage;
