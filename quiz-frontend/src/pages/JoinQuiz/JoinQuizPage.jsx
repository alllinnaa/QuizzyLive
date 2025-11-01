import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import "./JoinQuizPage.css";

function JoinQuizPage() {
  const navigate = useNavigate();
  const [quizId, setQuizId] = useState("");
  const [playerName, setPlayerName] = useState("");
  const [error, setError] = useState("");

  const handleJoin = (e) => {
    e.preventDefault();

    if (!quizId.trim() || !playerName.trim()) {
      setError("Будь ласка, введіть код вікторини (UUID) та ім’я!");
      return;
    }

    localStorage.setItem("playerName", playerName);
    navigate(`/quiz/${quizId}`); // ✅ передаємо повний UUID
  };

  return (
    <div className="join-page">
      <div className="logo" onClick={() => navigate("/")}>
        <span className="logo-text">QuizzyLive</span>
      </div>

      <div className="join-box">
        <h1 className="join-title">Приєднатись до вікторини</h1>

        <form onSubmit={handleJoin} className="join-form">
          <label>
            Код вікторини (UUID):
            <input
              type="text"
              value={quizId}
              onChange={(e) => setQuizId(e.target.value)}
              placeholder="Наприклад: be70d188-ad79-4cc0-907c-a2a4a3c2b65f"
              className="input-field"
            />
          </label>

          <label>
            Ваше ім’я:
            <input
              type="text"
              value={playerName}
              onChange={(e) => setPlayerName(e.target.value)}
              placeholder="Введіть ім’я"
              className="input-field"
            />
          </label>

          {error && <p className="error">{error}</p>}

          <button type="submit" className="join-btn">
            🚀 Приєднатись
          </button>
        </form>
      </div>
    </div>
  );
}

export default JoinQuizPage;
