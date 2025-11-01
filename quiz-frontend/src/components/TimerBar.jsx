import { useEffect, useState } from "react";

export default function TimerBar({ startedAt, durationMs }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 200);
    return () => clearInterval(id);
  }, []);

  if (!startedAt || !durationMs) return null;
  const end = startedAt + durationMs;
  const remaining = Math.max(0, end - now);
  const pct = Math.max(0, Math.min(100, (remaining / durationMs) * 100));

  return (
    <div style={{ border: "1px solid #ccc", borderRadius: 6, height: 12, width: "100%" }}>
      <div style={{ height: "100%", width: `${pct}%`, background: "#16a34a", transition: "width 0.2s" }} />
      <div style={{ fontSize: 12, marginTop: 4 }}>{Math.ceil(remaining / 1000)}s</div>
    </div>
  );
}