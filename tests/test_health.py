def test_health_ok(client, monkeypatch):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
