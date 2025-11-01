import { httpClient } from "./httpClient";

export const quizApi = {
  // Список для «Архів вікторин» (id, title, updatedAt)
  list: () => httpClient.get("/quizzes/"),

  // Повна вікторина з питаннями
  getById: (id) => httpClient.get(`/quizzes/${id}`),

  // Створити вікторину { title, questions: [{questionText, answers[4], correctAnswer}] }
  create: (payload) => httpClient.post("/quizzes/", payload),

  // Оновити (частково або повністю)
  update: (id, payload) => httpClient.put(`/quizzes/${id}`, payload),

  // Видалити
  remove: (id) => httpClient.delete(`/quizzes/${id}`),
};
export async function listQuizzes() {
  const res = await fetch(`${BASE}/quizzes/`);
  if (!res.ok) throw new Error("Failed to load quizzes");
  return res.json();
}

export async function getQuizQuestions(quizId) {
  // Очікується ендпоїнт типу: /api/v1/quizzes/{id}/questions/
  const res = await fetch(`${BASE}/quizzes/${quizId}/questions/`);
  if (!res.ok) throw new Error("Failed to load questions");
  return res.json();
}