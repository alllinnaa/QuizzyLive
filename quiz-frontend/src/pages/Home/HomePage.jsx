import "./HomePage.css";
import { useNavigate } from "react-router-dom";

function HomePage() {
  const navigate = useNavigate();

  return (
    <div className="app">
      {/* Логотип */}
      <div className="logo" onClick={() => navigate("/")}>
        <span className="logo-text">QuizzyLive</span>
      </div>

      <h1 className="title">QuizzyLive</h1>
      <p className="subtitle">
        Створюйте та грайте у вікторини в реальному часі!
      </p>
      <div className="buttons">
        <button className="btn create" onClick={() => navigate("/hostDashboard")}>
          Створити вікторину
        </button>
        <button className="btn join" onClick={() => navigate("/join")}>
          Приєднатись до гри
        </button>
      </div>
    </div>
  );
}

export default HomePage;
