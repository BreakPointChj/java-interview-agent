"""HTTP 接口基础行为测试。"""

from fastapi.testclient import TestClient

from interview_agent.api import app


def test_root_returns_web_application() -> None:
    """直接访问服务根地址时应返回面试应用，而不是 404。"""

    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "Java 全栈面试 Agent" in response.text
    assert "text/html" in response.headers["content-type"]


def test_health_endpoint() -> None:
    """健康检查应返回服务状态和支持领域。"""

    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
