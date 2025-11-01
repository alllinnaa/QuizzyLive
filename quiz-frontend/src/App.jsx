import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import HostRoom from "./pages/host/HostRoom";
import PlayerRoom from "./pages/player/PlayerRoom";

export default function App() {
  return (
    <BrowserRouter>
      <nav style={{ display: "flex", gap: 12, padding: 12 }}>
        <Link to="/host">Host</Link>
        <Link to="/play">Player</Link>
      </nav>
      <Routes>
        <Route path="/host" element={<HostRoom />} />
        <Route path="/host/:roomCode" element={<HostRoom />} />
        <Route path="/play" element={<PlayerRoom />} />
        <Route path="/play/:roomCode" element={<PlayerRoom />} />
        <Route path="*" element={<PlayerRoom />} />
      </Routes>
    </BrowserRouter>
  );
}