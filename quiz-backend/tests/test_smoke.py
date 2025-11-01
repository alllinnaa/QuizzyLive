from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_health():
    resp = client.get("/api/quizzes/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"