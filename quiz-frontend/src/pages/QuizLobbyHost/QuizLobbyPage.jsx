import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { quizApi } from "../../api/quizApi";
import { createQuizSocket } from "../../api/wsClient";
import "./QuizLobbyPage.css";

function QuizLobbyPage() {
  const navigate = useNavigate();
  const { id } = useParams(); // UUID вікторини
  const [quiz, setQuiz] = useState(null);
  const [participants, setParticipants] = useState([]);
  const [ws, setWs] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // ✅ Завантажуємо вікторину з бекенду
  useEffect(() => {
    const fetchQuiz = async () => {
      try {
        setLoading(true);
        const q = await quizApi.getById(id);
        setQuiz(q);
      } catch (e) {
        setError(e.message || "Помилка завантаження вікторини");
      } finally {
        setLoading(false);
      }
    };
    fetchQuiz();
  }, [id]);

  // ✅ WebSocket для ведучого
  useEffect(() => {
    if (!quiz) return;

    const socket = createQuizSocket({
      role: "host",
      roomCode: id, // ✅ використовуємо повний UUID
      onMessage: (msg) => {
        console.log("📨 host отримав:", msg);

        // ✅ Оновлення учасників
        if (msg.type === "state_sync") {
          if (msg.phase === "LOBBY" && msg.scoreboard) {
            setParticipants(msg.scoreboard);
          }
        } else if (msg.type === "player_joined") {
          // Додаємо нового учасника
          setParticipants(prev => {
            const exists = prev.find(p => p.name === msg.playerName);
            if (exists) return prev;
            return [...prev, { name: msg.playerName, score: 0 }];
          });
        } else if (msg.type === "player_left") {
          // Видаляємо учасника
          setParticipants(prev => 
            prev.filter(p => p.name !== msg.playerName)
          );
        }
      },
    });

    socket.onopen = () => {
      console.log("✅ WebSocket відкрито (host)");
      socket.sendJson({
        type: "host:create_session",
        roomCode: id, // ✅ повний UUID
        quizId: id,
        questions: quiz.questions.map((q) => ({
          id: q.id,
          question_text: q.questionText,
          answers: q.answers,
          correct_answer: q.correctAnswer,
          position: q.position,
        })),
      });
    };

    socket.onerror = (err) => console.error("⚠️ WebSocket помилка:", err);
    socket.onclose = () => console.warn("❌ WebSocket закрито (host)");

    setWs(socket);
    return () => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
    };
  }, [quiz, id]);

  // ✅ Почати вікторину
  const handleStartQuiz = () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      alert("WebSocket не підключено!");
      return;
    }
    
    // НЕ надсилаємо start_quiz тут, тільки переходимо до керування
    navigate(`/host-play/${id}`); // ✅ перехід до сторінки керування грою
  };

  const handleCancel = () => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.close();
    }
    navigate("/hostDashboard");
  };

  const handleCopyCode = () => {
    navigator.clipboard.writeText(id);
    alert(`Код вікторини скопійовано!`);
  };

  return (
    <div className="lobby-container">
      <div className="lobby-header">
        <button className="cancel-btn" onClick={handleCancel}>
          ↩ Назад
        </button>
        <h1>{quiz?.title || "Завантаження..."}</h1>
      </div>

      {error ? (
        <p className="error-text">{error}</p>
      ) : (
        <div className="lobby-content">
          <div className="lobby-code-box">
            <h2>Код для підключення:</h2>
            <div className="code">{id}</div>
            <button className="copy-btn" onClick={handleCopyCode}>
              📋 Скопіювати код
            </button>
            <p className="hint-text">
              Передайте цей код учасникам для підключення до вікторини
            </p>
          </div>

          <div className="participants-box">
            <h3>Учасники ({participants.length}):</h3>
            {participants.length === 0 ? (
              <p className="waiting-text">⏳ Очікуємо учасників...</p>
            ) : (
              <ul className="participants-list">
                {participants.map((p, i) => (
                  <li key={i} className="participant-item">
                    <span className="participant-avatar">👤</span>
                    <span className="participant-name">{p.name}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <button
            className="start-quiz-btn"
            onClick={handleStartQuiz}
            disabled={loading || !ws || ws.readyState !== WebSocket.OPEN}
          >
            🚀 Почати вікторину
          </button>
          
          {ws?.readyState !== WebSocket.OPEN && !loading && (
            <p className="warning-text">⚠️ Підключення до сервера...</p>
          )}
        </div>
      )}
    </div>
  );
}

export default QuizLobbyPage;