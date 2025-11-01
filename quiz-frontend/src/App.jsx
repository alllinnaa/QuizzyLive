import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import CreateQuizPage from "./pages/CreateQuiz/CreateQuizPage";
import QuizLobbyPage from "./pages/QuizLobbyHost/QuizLobbyPage";
import QuizHostPlayPage from "./pages/QuizHostPlay/QuizHostPlayPage";
import HomePage from "./pages/Home/HomePage";
import JoinQuizPage from "./pages/JoinQuiz/JoinQuizPage";
import QuizPlayPage from "./pages/QuizPlay/QuizPlayPage";

function App() {
  return (
    <Router>
      <Routes>
        {/* Головна сторінка */}
        <Route path="/" element={<HomePage/>}/>
        
        {/* Панель ведучого (список вікторин) */}
        <Route path="/hostDashboard" element={<CreateQuizPage />}/>
        
        {/* Лоббі ведучого (очікування учасників) */}
        <Route path="/lobby/:id" element={<QuizLobbyPage />} />
        
        {/* Гра ведучого (керування питаннями) */}
        <Route path="/host-play/:id" element={<QuizHostPlayPage />} />
        
        {/* Приєднання учасника */}
        <Route path="/join" element={<JoinQuizPage />} />
        
        {/* Гра учасника */}
        <Route path="/quiz/:quizId" element={<QuizPlayPage />} />
      </Routes>
    </Router>
  );
}

export default App;