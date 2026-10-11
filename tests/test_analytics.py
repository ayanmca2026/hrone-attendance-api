def test_employee_monthly(client):
    client.post("/employees", json={
        "emp_code": "EMP0001", "name": "A", "email": "a@a.com", "department": "Eng", "joined_on": "2026-01-01",
        "shift_start": "09:30", "shift_end": "18:30"
    })
    client.post("/attendance/punch-in", json={"emp_code": "EMP0001", "punched_at": 1767240000000}) # 2026-01-01 09:30 IST (Thursday)
    
    resp = client.get("/analytics/employees/EMP0001/monthly?month=2026-01")
    assert resp.status_code == 200
    assert resp.json()["working_days"] == 22 # 22 working days in Jan 2026
    assert resp.json()["present_days"] == 1.0
    assert resp.json()["attendance_pct"] == 4.55

def test_department_summary(client):
    client.post("/employees", json={
        "emp_code": "EMP0001", "name": "A", "email": "a@a.com", "department": "Eng", "joined_on": "2026-01-01",
        "shift_start": "09:30", "shift_end": "18:30"
    })
    client.post("/attendance/punch-in", json={"emp_code": "EMP0001", "punched_at": 1767240000000}) # 2026-01-01
    
    resp = client.get("/analytics/departments/summary?month=2026-01")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["department"] == "Eng"
    assert items[0]["headcount"] == 1
    assert items[0]["present_days"] == 1.0

def test_late_leaderboard(client):
    client.post("/employees", json={"emp_code": "EMP0001", "name": "A", "email": "a@a.com", "department": "Eng", "joined_on": "2026-01-01", "shift_start": "09:30", "shift_end": "18:30"})
    client.post("/employees", json={"emp_code": "EMP0002", "name": "B", "email": "b@b.com", "department": "Eng", "joined_on": "2026-01-01", "shift_start": "09:30", "shift_end": "18:30"})
    
    # A is late by 10 mins (09:40:01 = 1767240601000)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0001", "punched_at": 1767240601000})
    # B is late by 20 mins (09:50:01 = 1767241201000)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0002", "punched_at": 1767241201000})
    
    resp = client.get("/analytics/leaderboard/late?month=2026-01")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    assert items[0]["emp_code"] == "EMP0002"
    assert items[0]["rank"] == 1
    assert items[1]["emp_code"] == "EMP0001"
    assert items[1]["rank"] == 2

def test_department_trend(client):
    client.post("/employees", json={"emp_code": "EMP0001", "name": "A", "email": "a@a.com", "department": "Eng", "joined_on": "2026-01-01", "shift_start": "09:30", "shift_end": "18:30"})
    
    resp = client.get("/analytics/departments/Eng/trend?from=2026-01-01&to=2026-01-05")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 5
    assert items[0]["date"] == "2026-01-01"
    assert items[0]["headcount"] == 1


def test_department_summary_with_zero_logs_headcount(client):
    # Employee A has logs, Employee B has no logs but joined in January
    client.post("/employees", json={"emp_code": "EMP0010", "name": "A", "email": "a10@a.com", "department": "Sales", "joined_on": "2026-01-01"})
    client.post("/employees", json={"emp_code": "EMP0011", "name": "B", "email": "b11@b.com", "department": "Sales", "joined_on": "2026-01-15"})
    # Only A punches in
    client.post("/attendance/punch-in", json={"emp_code": "EMP0010", "punched_at": 1767240000000})

    resp = client.get("/analytics/departments/summary?month=2026-01&department=Sales")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["department"] == "Sales"
    assert items[0]["headcount"] == 2  # Both employees counted in headcount!
    assert items[0]["present_days"] == 1.0


def test_late_leaderboard_ties(client):
    client.post("/employees", json={"emp_code": "EMP0020", "name": "T1", "email": "t1@a.com", "department": "Eng", "joined_on": "2026-01-01"})
    client.post("/employees", json={"emp_code": "EMP0021", "name": "T2", "email": "t2@b.com", "department": "Eng", "joined_on": "2026-01-01"})

    # Both are late by 15 minutes (09:45:00 IST -> 1767240900000)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0020", "punched_at": 1767240900000})
    client.post("/attendance/punch-in", json={"emp_code": "EMP0021", "punched_at": 1767240900000})

    resp = client.get("/analytics/leaderboard/late?month=2026-01")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    # Ties share rank 1
    assert items[0]["rank"] == 1
    assert items[1]["rank"] == 1
    assert items[0]["total_late_minutes"] == 15
    assert items[1]["total_late_minutes"] == 15

