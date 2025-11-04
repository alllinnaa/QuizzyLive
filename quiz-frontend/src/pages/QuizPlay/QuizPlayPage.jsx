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
          case "state_sync":
            console.log("State sync:", msg.phase);
            setPhase(msg.phase || "WAITING");
            setConnectionStatus("connected");
            break;

          case "player_joined":
            console.log("Успішно приєдналися до вікторини!");
            setConnectionStatus("connected");
            setPhase("WAITING");
            break;

          case "question_started":
            console.log("Почалось питання:", msg.question);
            setQuestion(msg.question);
            setRemaining(Math.floor(msg.durationMs / 1000));
            setPhase("QUESTION_ACTIVE");
            setSelected(null);
            setCorrectAnswer(null);
            
            if (timerRef.current) clearInterval(timerRef.current);
            timerRef.current = setInterval(() => {
              setRemaining(prev => {
                if (prev <= 1) {
                  clearInterval(timerRef.current);
                  return 0;
                }
                return prev - 1;
              });
            }, 1000);
            break;

          case "answer_revealed":
            console.log("Показано відповідь:", msg.correctIndex);
            setPhase("REVEAL");
            setCorrectAnswer(msg.correctIndex);
            if (timerRef.current) clearInterval(timerRef.current);
            break;

          case "session_ended":
          case "quiz_ended":
            if (timerRef.current) clearInterval(timerRef.current);
            alert("Вікторина завершена!");
            navigate("/");
            break;

          case "error":
            console.error("Помилка від сервера:", msg.message);
            alert(`Помилка: ${msg.message}`);
            setConnectionStatus("error");
            if (msg.message?.includes("not found") || msg.message?.includes("does not exist")) {
              setTimeout(() => navigate("/join"), 2000);
            }
            break;

          default:
            console.log("Невідомий тип повідомлення:", msg.type);
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
      if (timerRef.current) clearInterval(timerRef.current);
    };

    socket.onerror = (error) => {
      console.error("WebSocket помилка:", error);
      setConnectionStatus("error");
    };

    setWs(socket);

    return () => {
      console.log("Очищення WebSocket з'єднання");
      if (timerRef.current) clearInterval(timerRef.current);
      if (socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
      wsInitialized.current = false;
    };
  }, [quizId, navigate]);

  const handleAnswer = (idx) => {
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

  if (connectionStatus === "connecting" || phase === "CONNECTING") {
    return (
      <div className="quiz-play-page">
        <div className="status-box">
          <h2>Підключення до вікторини...</h2>
          <p>Код: {quizId}</p>
          <p>Ім'я: {playerName}</p>
        </div>
      </div>
    );
  }

  if (connectionStatus === "error") {
    return (
      <div className="quiz-play-page">
        <div className="status-box error">
          <h2>Помилка підключення</h2>
          <p>Не вдалося підключитися до вікторини</p>
          <p>Перевірте код вікторини та спробуйте ще раз</p>
          <button onClick={() => navigate("/join")}>
            Повернутись
          </button>
        </div>
      </div>
    );
  }

  if (connectionStatus === "disconnected") {
    return (
      <div className="quiz-play-page">
        <div className="status-box error">
          <h2>З'єднання втрачено</h2>
          <p>Зв'язок з сервером перервано</p>
          <button onClick={() => window.location.reload()}>
            Перепідключитись
          </button>
          <button onClick={() => navigate("/join")}>
            Повернутись
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="quiz-play-page">
      <div className="player-header">
        <span className="player-name">{playerName}</span>
        <span className="connection-status">
          {connectionStatus === "connected" ? "Підключено" : "Відключено"}
        </span>
      </div>

      {phase === "WAITING" && (
        <div className="waiting-box">
          <h2>Очікуємо початку вікторини...</h2>
          <p>Ведучий почне гру незабаром</p>
          <div className="pulse-indicator">●</div>
        </div>
      )}

      {phase === "QUESTION_ACTIVE" && question && (
        <div className="question-box">
          <div className="question-header">
            <h3>Питання {question.position + 1}</h3>
            <div className={`timer ${remaining <= 5 ? 'urgent' : ''}`}>
              {remaining} сек
            </div>
          </div>

          <h2 className="question-text">{question.question_text}</h2>

          <div className="answers-grid">
            {question.answers.map((ans, i) => (
              <button
                key={i}
                className={`answer-btn ${selected === i ? 'selected' : ''}`}
                disabled={selected !== null}
                onClick={() => handleAnswer(i)}
              >
                <span className="answer-number">{i + 1}</span>
                <span className="answer-text">{ans}</span>
              </button>
            ))}
          </div>

          {selected !== null && (
            <p className="answer-submitted">Відповідь надіслано!</p>
          )}
        </div>
      )}

      {phase === "REVEAL" && question && (
        <div className="reveal-box">
          <h2>Результати</h2>
          <p className="question-text">{question.question_text}</p>

          <div className="answers-grid">
            {question.answers.map((ans, i) => (
              <div
                key={i}
                className={`answer-result ${
                  i === correctAnswer ? 'correct' : ''
                } ${i === selected ? 'selected' : ''}`}
              >
                <span className="answer-number">{i + 1}</span>
                <span className="answer-text">{ans}</span>
                {i === correctAnswer && <span className="check">✓</span>}
                {i === selected && i !== correctAnswer && <span className="cross">✗</span>}
              </div>
            ))}
          </div>

          {selected === correctAnswer && (
            <p className="result-message success">Правильно! +100 балів</p>
          )}
          {selected !== correctAnswer && selected !== null && (
            <p className="result-message wrong">Неправильно. Правильна відповідь: {correctAnswer + 1}</p>
          )}
          {selected === null && (
            <p className="result-message missed">Час вийшов!</p>
          )}

          <div className="waiting-next">
            <p>Очікуємо наступного питання...</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default QuizPlayPage;