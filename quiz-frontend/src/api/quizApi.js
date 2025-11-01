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