import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import CreateQuizPage from "./pages/CreateQuiz/CreateQuizPage";

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<CreateQuizPage />}/>
      </Routes>
    </Router>
  );
}

export default App;
