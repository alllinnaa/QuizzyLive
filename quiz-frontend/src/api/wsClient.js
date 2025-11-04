export const WS_BASE_URL =
  import.meta.env.VITE_WS_BASE_URL || "ws://localhost:8000/ws";

export function createQuizSocket({ role, roomCode, name, onMessage }) {
  // Формуємо URL з параметрами
  const params = new URLSearchParams({
    role: role,
    roomCode: roomCode
  });
  
  if (name) {
    params.append('name', name);
  }
  
  const url = `${WS_BASE_URL}?${params.toString()}`;
  console.log("Підключення до:", url);

  const socket = new WebSocket(url);

  socket.onopen = () => {
    console.log(" WebSocket підключено:", { role, roomCode, name });
  };

  socket.onclose = (event) => {
    console.log(" WebSocket закрито:", {
      code: event.code,
      reason: event.reason,
      wasClean: event.wasClean
    });
  };

  socket.onerror = (err) => {
    console.error("WebSocket помилка:", err);
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      console.log("Отримано повідомлення:", data);
      onMessage?.(data);
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