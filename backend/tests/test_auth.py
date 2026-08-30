from fastapi.testclient import TestClient

from app.main import app


def test_login_success(student):
    with TestClient(app) as client:
        resp = client.post(
            "/auth/login", json={"email": student.email, "access_code": "pw123"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["student"]["email"] == student.email
        assert body["token"]


def test_login_wrong_access_code(student):
    with TestClient(app) as client:
        resp = client.post(
            "/auth/login", json={"email": student.email, "access_code": "wrong-code"}
        )
        assert resp.status_code == 401


def test_login_unknown_email(student):
    with TestClient(app) as client:
        resp = client.post(
            "/auth/login", json={"email": "nobody@example.edu", "access_code": "x"}
        )
        assert resp.status_code == 401
