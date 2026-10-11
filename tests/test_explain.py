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

