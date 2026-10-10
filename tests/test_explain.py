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
