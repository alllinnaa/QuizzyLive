import { API_BASE_URL } from "../config";

const defaultHeaders = { "Content-Type": "application/json" };

async function request(path, { method = "GET", body, headers = {}, signal } = {}) {
  const resp = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: { ...defaultHeaders, ...headers },
    body: body ? JSON.stringify(body) : undefined,
    signal,
    credentials: "include", // якщо знадобиться cookie/JWT в майбутньому
  });

  if (!resp.ok) {
    let errText = `${resp.status} ${resp.statusText}`;
    try {
      const data = await resp.json();
      errText = data?.detail || errText;
    } catch (_) {}
    const error = new Error(errText);
    error.status = resp.status;
    throw error;
  }

  // 204 No Content
  if (resp.status === 204) return null;

  const contentType = resp.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return resp.json();
  }
  return resp.text();
}

export const httpClient = {
  get: (path, opts) => request(path, { method: "GET", ...(opts || {}) }),
  post: (path, body, opts) => request(path, { method: "POST", body, ...(opts || {}) }),
  put: (path, body, opts) => request(path, { method: "PUT", body, ...(opts || {}) }),
  delete: (path, opts) => request(path, { method: "DELETE", ...(opts || {}) }),
};