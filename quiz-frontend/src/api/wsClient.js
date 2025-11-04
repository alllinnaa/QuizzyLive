export const WS_BASE_URL =
  import.meta.env.VITE_WS_BASE_URL || "ws://localhost:8000/ws";

let quizSocket = null;
let quizSocketParams = null;
let currentOnMessage = null;

function buildUrl({ role, roomCode, name }) {
  const params = new URLSearchParams({ role: role, roomCode: roomCode });
  if (name) {
    params.append("name", name);
  }
  return `${WS_BASE_URL}?${params.toString()}`;
}

export function createQuizSocket({ role, roomCode, name, onMessage }) {
  currentOnMessage = onMessage || null;

  const url = buildUrl({ role, roomCode, name });

  if (
    quizSocket &&
    (quizSocket.readyState === WebSocket.OPEN ||
      quizSocket.readyState === WebSocket.CONNECTING)
  ) {
    console.log("Використовуємо існуючий WebSocket:", { url, role, roomCode, name });
    return quizSocket;
  }

  if (
    quizSocket &&
    (quizSocket.readyState === WebSocket.CLOSING ||
      quizSocket.readyState === WebSocket.CLOSED)
  ) {
    try {
      quizSocket.close();
    } catch (e) {
      console.warn("Помилка при закритті попереднього WebSocket:", e);
    }
    quizSocket = null;
  }

  console.log("Створення нового WebSocket-підключення:", {
    url,
    role,
    roomCode,
    name,
  });

  const socket = new WebSocket(url);
  quizSocket = socket;
  quizSocketParams = { role, roomCode, name };

  socket.onopen = () => {
    console.log("WebSocket підключено:", quizSocketParams);
  };

  socket.onclose = (event) => {
    console.log("WebSocket закрито:", {
      code: event.code,
      reason: event.reason,
      wasClean: event.wasClean,
    });
    quizSocket = null;
  };

  socket.onerror = (err) => {
    console.error("WebSocket помилка:", err);
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      console.log("Отримано повідомлення:", data);
      if (currentOnMessage) {
        currentOnMessage(data);
      }
    } catch (err) {
      console.error("JSON parse error:", err, "Data:", event.data);
    }
  };

  socket.sendJson = (obj) => {
    if (socket.readyState === WebSocket.OPEN) {
      console.log("Надсилаємо:", obj);
      socket.send(JSON.stringify(obj));
    } else {
      console.warn("WebSocket не готовий, стан:", socket.readyState);
    }
  };

  return socket;
}

export function getExistingQuizSocket() {
  return quizSocket;
}
