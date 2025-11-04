import React, { useEffect, useState, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { quizApi } from "../../api/quizApi";
import { createQuizSocket } from "../../api/wsClient";
import "./QuizHostPlayPage.css";

function QuizHostPlayPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [ws, setWs] = useState(null);
  const [quiz, setQuiz] = useState(null);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [scoreboard, setScoreboard] = useState([]);
  const [phase, setPhase] = useState("LOBBY");
  const [remainingTime, setRemainingTime] = useState(0);
  const [loading, setLoading] = useState(true);
  
  const [isSettingTime, setIsSettingTime] = useState(false);
  const [timeForQuestion, setTimeForQuestion] = useState(30);
  
  const wsInitialized = useRef(false);

  useEffect(() => {
    const fetchQuiz = async () => {
      try {
        const data = await quizApi.getById(id);
        setQuiz(data);
      } catch (err) {
        alert("Помилка завантаження: " + err.message);
        navigate("/hostDashboard");
      } finally {
        setLoading(false);
      }
    };
    fetchQuiz();
  }, [id, navigate]);

  useEffect(() => {
    if (!quiz || wsInitialized.current) return;
    
    wsInitialized.current = true;
    console.log("Підключення ведучого до гри, roomCode:", id);

    const socket = createQuizSocket({
      role: "host",
      roomCode: id,
      onMessage: (msg) => {
        console.log("Host (play) отримав:", msg);

        if (msg.type === "state_sync") {
          console.log("State sync:", msg);
          setPhase(msg.phase || "LOBBY");
          
          if (msg.scoreboard && Array.isArray(msg.scoreboard)) {
            console.log("Оновлення scoreboard з state_sync:", msg.scoreboard);
            setScoreboard(msg.scoreboard);
          }
          
          if (msg.question) {
            setCurrentQuestion(msg.question);
            setQuestionIndex(msg.questionIndex || 0);
          }
        } 
        else if (msg.type === "question_started") {
          console.log("Питання почалось:", msg.question);
          setCurrentQuestion(msg.question);
          setQuestionIndex(msg.questionIndex);
          setRemainingTime(Math.floor(msg.durationMs / 1000));
          setPhase("QUESTION_ACTIVE");
          setIsSettingTime(false);
        } 
        else if (msg.type === "answer_revealed") {
          console.log("Відповідь розкрито");
          setPhase("REVEAL");
          
          if (msg.scoreboard && Array.isArray(msg.scoreboard)) {
            console.log("Оновлення scoreboard після reveal:", msg.scoreboard);
            setScoreboard(msg.scoreboard);
          }
        } 
        else if (msg.type === "scoreboard_updated") {
          console.log("Оновлення scoreboard:", msg.scoreboard);
          setScoreboard(msg.scoreboard);
        }
        else if (msg.type === "player_joined") {
          console.log("Новий учасник:", msg.playerName);
          
          setScoreboard(prev => {
            const exists = prev.find(p => p.name === msg.playerName || p.playerId === msg.playerId);
            if (exists) {
              console.log("Учасник вже існує:", msg.playerName);
              return prev;
            }
            console.log("Додаємо учасника:", msg.playerName);
            return [...prev, { 
              name: msg.playerName, 
              playerId: msg.playerId,
              score: 0 
            }];
          });
        }
        else if (msg.type === "player_left") {
          console.log("Учасник вийшов:", msg.playerName);
          setScoreboard(prev => prev.filter(p => p.name !== msg.playerName));
        }
      },
    });

    socket.onopen = () => {
      console.log("WebSocket host (play) підключено");
    };

    socket.onerror = (err) => {
      console.error("WebSocket помилка:", err);
    };

    socket.onclose = () => {
      console.log("WebSocket закрито");
      wsInitialized.current = false;
    };

    setWs(socket);

    return () => {
      console.log("Закриваємо WebSocket (play cleanup)");
      if (socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
      wsInitialized.current = false;
    };
  }, [quiz, id]);

  useEffect(() => {
    if (phase === "QUESTION_ACTIVE" && remainingTime > 0) {
      const timer = setInterval(() => {
        setRemainingTime(prev => {
          if (prev <= 1) {
            clearInterval(timer);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [phase, remainingTime]);

  const handlePrepareQuestion = () => {
    if (questionIndex >= quiz.questions.length) {
      alert("Це було останнє питання!");
      handleEndQuiz();
      return;
    }
    setIsSettingTime(true);
  };

  const handleStartQuestion = () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      alert("WebSocket не підключено!");
      return;
    }

    console.log("Запуск питання з часом:", timeForQuestion);
    ws.sendJson({
      type: "host:next_question",
      durationMs: timeForQuestion * 1000,
    });
  };

  const handleRevealAnswer = () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    console.log("Розкриття відповіді");
    ws.sendJson({
      type: "host:reveal_answer",
    });
  };

  const handleNextQuestion = () => {
    const nextIndex = questionIndex + 1;
    if (nextIndex >= quiz.questions.length) {
      alert("Це було останнє питання!");
      handleEndQuiz();
    } else {
      setQuestionIndex(nextIndex);
      setPhase("LOBBY");
      setIsSettingTime(true);
      setTimeForQuestion(30);
    }
  };

  const handleEndQuiz = () => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      navigate("/hostDashboard");
      return;
    }

    console.log("Завершення вікторини");
    ws.sendJson({
      type: "host:end_session",
    });

    setTimeout(() => {
      navigate("/hostDashboard");
    }, 1000);
  };

  if (loading) {
    return (
      <div className="quiz-play-container">
        <p className="loading">⏳ Завантаження...</p>
      </div>
    );
  }

  if (!quiz) {
    return (
      <div className="quiz-play-container">
        <p className="error">Вікторину не знайдено</p>
      </div>
    );
  }

  const totalQuestions = quiz.questions?.length || 0;

  return (
    <div className="quiz-play-container">
      <header className="quiz-header">
        <h1>{quiz.title}</h1>
        <div className="header-info">
          <span>Питання {questionIndex + 1} / {totalQuestions}</span>
          <span>Учасників: {scoreboard.length}</span>
        </div>
        <button className="end-quiz-btn" onClick={handleEndQuiz}>
          Завершити
        </button>
      </header>

      <div className="host-content">
        {isSettingTime && (
          <div className="time-setting-box">
            <h2>Встановіть час для питання</h2>
            {quiz.questions[questionIndex] && (
              <p className="question-preview">
                {quiz.questions[questionIndex].questionText}
              </p>
            )}

            <div className="time-input-group">
              <label htmlFor="timeInput">Час (секунди):</label>
              <input
                id="timeInput"
                type="number"
                min="5"
                max="300"
                value={timeForQuestion}
                onChange={(e) => setTimeForQuestion(Number(e.target.value))}
                className="time-input"
              />
            </div>

            <button className="start-question-btn" onClick={handleStartQuestion}>
              Почати питання
            </button>
          </div>
        )}

        {phase === "QUESTION_ACTIVE" && currentQuestion && (
          <div className="question-active-box">
            <div className="timer-display">
              <span className={remainingTime <= 5 ? "time-critical" : ""}>
                {remainingTime}с
              </span>
            </div>

            <div className="question-box">
              <h2>{currentQuestion.question_text}</h2>

              <ul className="answers-list">
                {currentQuestion.answers?.map((answer, idx) => (
                  <li key={idx} className="answer-option">
                    <span className="option-number">{idx + 1}</span>
                    <span className="option-text">{answer}</span>
                  </li>
                ))}
              </ul>
            </div>

            <button className="reveal-btn" onClick={handleRevealAnswer}>
              Показати відповідь
            </button>
          </div>
        )}

        {phase === "REVEAL" && currentQuestion && (
          <div className="reveal-box">
            <h2>Правильна відповідь:</h2>

            <div className="question-box">
              <p className="question-text">{currentQuestion.question_text}</p>

              <ul className="answers-list">
                {currentQuestion.answers?.map((answer, idx) => (
                  <li
                    key={idx}
                    className={`answer-option ${
                      idx === currentQuestion.correct_answer ? "correct" : ""
                    }`}
                  >
                    <span className="option-number">{idx + 1}</span>
                    <span className="option-text">{answer}</span>
                    {idx === currentQuestion.correct_answer && (
                      <span className="checkmark">✓</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>

            {questionIndex < totalQuestions - 1 ? (
              <button className="next-btn" onClick={handleNextQuestion}>
                Наступне питання
              </button>
            ) : (
              <button className="finish-btn" onClick={handleEndQuiz}>
                Завершити вікторину
              </button>
            )}
          </div>
        )}

        {(phase === "LOBBY" || phase === "WAITING") && !isSettingTime && (
          <div className="waiting-box">
            <p>Готово до старту</p>
            <button className="prepare-btn" onClick={handlePrepareQuestion}>
              Підготувати питання
            </button>
          </div>
        )}

        <div className="scoreboard-section">
          <h3>Таблиця лідерів ({scoreboard.length})</h3>
          {scoreboard.length > 0 ? (
            <ol className="scoreboard-list">
              {scoreboard
                .sort((a, b) => b.score - a.score)
                .map((player, i) => (
                  <li key={player.playerId || i} className="scoreboard-item">
                    <span className="player-rank">#{i + 1}</span>
                    <span className="player-name">{player.name}</span>
                    <span className="player-score">{player.score} балів</span>
                  </li>
                ))}
            </ol>
          ) : (
            <p className="no-players">Немає учасників. Очікуємо підключення...</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default QuizHostPlayPage;