from unittest.mock import patch
from app.main import db


def test_health_ok(client, monkeypatch):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_db_unavailable(client):
    with patch.object(db, "command", side_effect=Exception("Connection lost")):
        response = client.get("/health")
        assert response.status_code == 503
        assert response.json() == {"detail": "MongoDB unavailable"}

