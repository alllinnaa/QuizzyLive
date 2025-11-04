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
        <Route path="/" element={<HomePage/>}/>      
        <Route path="/hostDashboard" element={<CreateQuizPage />}/>
        <Route path="/lobby/:id" element={<QuizLobbyPage />} />    
        <Route path="/host-play/:id" element={<QuizHostPlayPage />} />    
        <Route path="/join" element={<JoinQuizPage />} />     
        <Route path="/quiz/:quizId" element={<QuizPlayPage />} />
      </Routes>
    </Router>
  );
}

export default App;