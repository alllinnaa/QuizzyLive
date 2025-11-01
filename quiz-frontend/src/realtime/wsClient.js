export function createWS({ role, roomCode, name }) {
  const WS_URL = import.meta.env.VITE_WS_URL;
  const url = new URL(WS_URL);
  url.searchParams.set("role", role);
  url.searchParams.set("roomCode", roomCode);
  if (name) url.searchParams.set("name", name);

  const ws = new WebSocket(url);
  return ws;
}
