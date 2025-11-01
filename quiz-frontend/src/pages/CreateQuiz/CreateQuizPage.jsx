import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { quizApi } from "../../api/quizApi";
import "./CreateQuizPage.css";

function CreateQuizPage() {
  const navigate = useNavigate();

  // ------------------------------
  // СТАН ФОРМИ (створення/редагування)
  // ------------------------------
  const [quizTitle, setQuizTitle] = useState("");
  const [questions, setQuestions] = useState([
    { questionText: "", answers: ["", "", "", ""], correctAnswer: null },
  ]);

  const [isEditing, setIsEditing] = useState(false);
  const [editingQuizId, setEditingQuizId] = useState(null);

  // ------------------------------
  // СТАН АРХІВУ
  // ------------------------------
  const [archive, setArchive] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const archiveMap = useMemo(() => {
    const m = new Map();
    archive.forEach((q) => m.set(q.id, q));
    return m;
  }, [archive]);

  // ------------------------------
  // HELPERS
  // ------------------------------
  const resetToCreateMode = () => {
    setIsEditing(false);
    setEditingQuizId(null);
    setQuizTitle("");
    setQuestions([{ questionText: "", answers: ["", "", "", ""], correctAnswer: null }]);
  };

  const validateQuiz = (title, qs) => {
    if (!title.trim()) {
      alert("Будь ласка, введіть назву вікторини!");
      return false;
    }
    if (!qs.length) {
      alert("Додайте принаймні одне питання!");
      return false;
    }
    for (let i = 0; i < qs.length; i++) {
      const q = qs[i];
      if (!q.questionText.trim()) {
        alert(`Питання ${i + 1}: текст не може бути порожнім.`);
        return false;
      }
      if (q.answers.some((a) => !a.trim())) {
        alert(`Питання ${i + 1}: усі 4 варіанти відповіді мають бути заповнені.`);
        return false;
      }
      if (q.correctAnswer === null || q.correctAnswer < 0 || q.correctAnswer > 3) {
        alert(`Питання ${i + 1}: виберіть правильну відповідь.`);
        return false;
      }
    }
    return true;
  };

  // ------------------------------
  // API CALLS
  // ------------------------------
  const fetchArchive = async () => {
    setLoading(true);
    setError("");
    try {
      const items = await quizApi.list();
      setArchive(items);
    } catch (e) {
      setError(e.message || "Помилка завантаження архіву");
    } finally {
      setLoading(false);
    }
  };

  const fetchQuizAndEdit = async (id) => {
    setLoading(true);
    setError("");
    try {
      const data = await quizApi.getById(id);
      setIsEditing(true);
      setEditingQuizId(id);
      setQuizTitle(data.title);
      setQuestions(
        data.questions.map((qq) => ({
          questionText: qq.questionText,
          answers: [...qq.answers],
          correctAnswer: qq.correctAnswer,
        }))
      );
    } catch (e) {
      setError(e.message || "Не вдалося завантажити вікторину");
    } finally {
      setLoading(false);
    }
  };

  const createQuiz = async () => {
    if (!validateQuiz(quizTitle, questions)) return;
    setLoading(true);
    setError("");
    try {
      await quizApi.create({ title: quizTitle.trim(), questions });
      await fetchArchive();
      alert("Вікторину успішно збережено!");
      resetToCreateMode();
    } catch (e) {
      setError(e.message || "Помилка створення вікторини");
    } finally {
      setLoading(false);
    }
  };

  const updateQuiz = async () => {
    if (!validateQuiz(quizTitle, questions)) return;
    if (!editingQuizId) return;
    setLoading(true);
    setError("");
    try {
      await quizApi.update(editingQuizId, { title: quizTitle.trim(), questions });
      await fetchArchive();
      alert("Вікторину оновлено!");
      resetToCreateMode();
    } catch (e) {
      setError(e.message || "Помилка оновлення вікторини");
    } finally {
      setLoading(false);
    }
  };

  const deleteQuiz = async (id) => {
    if (!window.confirm("Видалити цю вікторину безповоротно?")) return;
    setLoading(true);
    setError("");
    try {
      await quizApi.remove(id);
      await fetchArchive();
      if (isEditing && editingQuizId === id) {
        resetToCreateMode();
      }
    } catch (e) {
      setError(e.message || "Помилка видалення вікторини");
    } finally {
      setLoading(false);
    }
  };

  // ------------------------------
  // INIT
  // ------------------------------
  useEffect(() => {
    fetchArchive();
  }, []);

  // ------------------------------
  // ХЕНДЛЕРИ ДЛЯ ПИТАНЬ (локальна форма)
  // ------------------------------
  const handleAddQuestion = () => {
    setQuestions((prev) => [
      ...prev,
      { questionText: "", answers: ["", "", "", ""], correctAnswer: null },
    ]);
  };

  const handleRemoveQuestion = (index) => {
    setQuestions((prev) => {
      const updated = [...prev];
      updated.splice(index, 1);
      return updated.length
        ? updated
        : [{ questionText: "", answers: ["", "", "", ""], correctAnswer: null }];
    });
  };

  const handleQuestionChange = (index, value) => {
    setQuestions((prev) => {
      const updated = [...prev];
      updated[index] = { ...updated[index], questionText: value };
      return updated;
    });
  };

  const handleAnswerChange = (qIndex, aIndex, value) => {
    setQuestions((prev) => {
      const updated = [...prev];
      const ans = [...updated[qIndex].answers];
      ans[aIndex] = value;
      updated[qIndex] = { ...updated[qIndex], answers: ans };
      return updated;
    });
  };

  const handleSetCorrectAnswer = (qIndex, aIndex) => {
    setQuestions((prev) => {
      const updated = [...prev];
      updated[qIndex] = { ...updated[qIndex], correctAnswer: aIndex };
      return updated;
    });
  };

  // ------------------------------
  // РЕНДЕР
  // ------------------------------
  return (   
    <div className="create-quiz-container two-columns">
      <div className="logo" onClick={() => navigate("/")}>
        <span className="logo-text">QuizzyLive</span>
      </div>
      {/* Ліва колонка: створення/редагування */}
      <div className="left-pane">
        <button className="cancel-btn" onClick={() => navigate("/")}>
          ✖ Скасувати
        </button>

        <div className="quiz-form">
          <h2>{isEditing ? "Редагування вікторини" : "Створення вікторини"}</h2>
          {error ? <div className="error-box">{error}</div> : null}
          {loading ? <div className="loading-box">Завантаження...</div> : null}

          <input
            type="text"
            placeholder="Назва вікторини"
            value={quizTitle}
            onChange={(e) => setQuizTitle(e.target.value)}
            className="quiz-title-input"
          />

          {questions.map((q, qIndex) => (
            <div key={qIndex} className="question-block">
              <div className="question-header">
                <h3>Питання {qIndex + 1}</h3>
                <button
                  className="remove-question-btn"
                  onClick={() => handleRemoveQuestion(qIndex)}
                >
                  🗑 Видалити
                </button>
              </div>

              <input
                type="text"
                placeholder="Текст питання"
                value={q.questionText}
                onChange={(e) => handleQuestionChange(qIndex, e.target.value)}
                className="question-input"
              />

              <div className="answers-container">
                {q.answers.map((answer, aIndex) => (
                  <div key={aIndex} className="answer-option">
                    <input
                      type="text"
                      placeholder={`Відповідь ${aIndex + 1}`}
                      value={answer}
                      onChange={(e) => handleAnswerChange(qIndex, aIndex, e.target.value)}
                      className="answer-input"
                    />
                    <label>
                      <input
                        type="radio"
                        name={`correct-${qIndex}`}
                        checked={q.correctAnswer === aIndex}
                        onChange={() => handleSetCorrectAnswer(qIndex, aIndex)}
                      />
                      Правильна
                    </label>
                  </div>
                ))}
              </div>
            </div>
          ))}

          <div className="form-actions">
            <button className="add-question-btn" onClick={handleAddQuestion}>
              ➕ Додати питання
            </button>
            {!isEditing ? (
              <button className="save-quiz-btn" onClick={createQuiz}>
                💾 Зберегти вікторину
              </button>
            ) : (
              <>
                <button className="save-quiz-btn" onClick={updateQuiz}>
                  🔄 Оновити вікторину
                </button>
                <button className="secondary-btn" onClick={resetToCreateMode}>
                  ↩ Лишити як є
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Права колонка: Архів вікторин */}
      <div className="right-pane">
        <div className="archive-header">
          <h2>Архів вікторин</h2>
          <button className="refresh-btn" onClick={fetchArchive} disabled={loading}>
            ⟳ оновити
          </button>
        </div>

        {archive.length === 0 ? (
          <p className="archive-empty">Архів порожній. Збережіть першу вікторину.</p>
        ) : (
          <ul className="archive-list">
            {archive.map((q) => (
              <li key={q.id} className="archive-item">
                <span className="archive-title">{q.title}</span>
                <div className="archive-actions">
                  <button
                    className="start-btn"
                    onClick={() => navigate(`/lobby/${q.id}`)}
                    title="Почати вікторину"
                  >
                    🎮 почати
                  </button>
                  <button
                    className="edit-btn"
                    onClick={() => fetchQuizAndEdit(q.id)}
                    title="Редагувати"
                  >
                    ✏ змінити
                  </button>
                  <button
                    className="delete-btn"
                    onClick={() => deleteQuiz(q.id)}
                    title="Видалити"
                  >
                    🗑 видалити
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default CreateQuizPage;