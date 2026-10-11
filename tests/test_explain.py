import pytest


def test_explain_attendance_list(client):
    resp = client.get("/admin/explain/attendance_list")
    assert resp.status_code == 200
    data = resp.json()
    assert data["endpoint"] == "attendance_list"
    assert data["collection"] == "attendance_logs"
    assert "explain" in data


def test_explain_employee_monthly(client):
    resp = client.get("/admin/explain/employee_monthly?emp_code=EMP0001&month=2026-01")
    assert resp.status_code == 200


def test_explain_missing_param(client):
    resp = client.get("/admin/explain/employee_monthly?emp_code=EMP0001")
    assert resp.status_code == 422


def test_explain_other_endpoints(client):
    # department_summary
    resp = client.get("/admin/explain/department_summary?month=2026-01")
    assert resp.status_code == 200
    assert resp.json()["endpoint"] == "department_summary"
    assert resp.json()["collection"] == "employees"

    # late_leaderboard
    resp2 = client.get("/admin/explain/late_leaderboard?month=2026-01")
    assert resp2.status_code == 200
    assert resp2.json()["endpoint"] == "late_leaderboard"
    assert resp2.json()["collection"] == "attendance_logs"

    # department_trend
    resp3 = client.get("/admin/explain/department_trend?department=Eng&from=2026-01-01&to=2026-01-05")
    assert resp3.status_code == 200
    assert resp3.json()["endpoint"] == "department_trend"
    assert resp3.json()["collection"] == "employees"


def test_explain_disabled_in_production(client, monkeypatch):
    import app.main
    monkeypatch.setattr(app.main, "ENABLE_ADMIN_EXPLAIN", False)

    resp = client.get("/admin/explain/attendance_list")
    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()


def test_explain_admin_api_key_authorization(client, monkeypatch):
    import app.main
    monkeypatch.setattr(app.main, "ENABLE_ADMIN_EXPLAIN", True)
    monkeypatch.setattr(app.main, "ADMIN_API_KEY", "secure_ops_key_123")

    # Missing header -> 403
    resp1 = client.get("/admin/explain/attendance_list")
    assert resp1.status_code == 403

    # Invalid header -> 403
    resp2 = client.get("/admin/explain/attendance_list", headers={"X-Admin-Key": "wrong_key"})
    assert resp2.status_code == 403

    # Valid header -> 200
    resp3 = client.get("/admin/explain/attendance_list", headers={"X-Admin-Key": "secure_ops_key_123"})
    assert resp3.status_code == 200


def test_explain_parameter_validation(client):
    # Invalid page (< 1)
    r1 = client.get("/admin/explain/attendance_list?page=0")
    assert r1.status_code == 422

    # Invalid page_size (> 100)
    r2 = client.get("/admin/explain/attendance_list?page_size=101")
    assert r2.status_code == 422

    # Invalid limit (> 50)
    r3 = client.get("/admin/explain/late_leaderboard?month=2026-01&limit=55")
    assert r3.status_code == 422

    # Invalid date_from format
    r4 = client.get("/admin/explain/attendance_list?date_from=not-a-date")
    assert r4.status_code == 422

    # date_from > date_to
    r5 = client.get("/admin/explain/attendance_list?date_from=2026-02-01&date_to=2026-01-01")
    assert r5.status_code == 422

    # Invalid status
    r6 = client.get("/admin/explain/attendance_list?status=NONEXISTENT_STATUS")
    assert r6.status_code == 422

    # department_trend range > 92 days
    r7 = client.get("/admin/explain/department_trend?department=Eng&from=2026-01-01&to=2026-05-01")
    assert r7.status_code == 422
