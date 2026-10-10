def test_punch_in(client):
    # Setup
    client.post("/employees", json={
        "emp_code": "EMP0001", "name": "A", "email": "a@a.com", "department": "Eng", "joined_on": "2026-01-01",
        "shift_start": "09:30", "shift_end": "18:30"
    })

    # Punch in exactly on time
    # 2026-01-01 09:30:00 IST -> 2026-01-01 04:00:00 UTC = 1767240000000
    resp = client.post("/attendance/punch-in", json={
        "emp_code": "EMP0001",
        "punched_at": 1767240000000
    })
    assert resp.status_code == 201
    assert resp.json()["date"] == "2026-01-01"
    assert resp.json()["late_minutes"] == 0

    # Duplicate
    resp2 = client.post("/attendance/punch-in", json={"emp_code": "EMP0001", "punched_at": 1767240000000})
    assert resp2.status_code == 409

def test_punch_in_late(client):
    client.post("/employees", json={
        "emp_code": "EMP0001", "name": "A", "email": "a@a.com", "department": "Eng", "joined_on": "2026-01-01",
        "shift_start": "09:30", "shift_end": "18:30"
    })
    # Punch in 09:40:01 IST -> 04:10:01 UTC = 1767240601000
    resp = client.post("/attendance/punch-in", json={
        "emp_code": "EMP0001",
        "punched_at": 1767240601000
    })
    assert resp.status_code == 201
    assert resp.json()["late_minutes"] == 10

def test_punch_out(client):
    client.post("/employees", json={
        "emp_code": "EMP0001", "name": "A", "email": "a@a.com", "department": "Eng", "joined_on": "2026-01-01",
        "shift_start": "09:30", "shift_end": "18:30"
    })
    client.post("/attendance/punch-in", json={"emp_code": "EMP0001", "punched_at": 1767240000000}) # 09:30 IST

    # Punch out at 18:30 IST (1767272400000)
    resp = client.post("/attendance/punch-out", json={"emp_code": "EMP0001", "punched_at": 1767272400000})
    assert resp.status_code == 200
    assert resp.json()["work_hours"] == 9.0
    assert resp.json()["half_day"] == False

    # Already punched out
    resp2 = client.post("/attendance/punch-out", json={"emp_code": "EMP0001", "punched_at": 1767272400000})
    assert resp2.status_code == 409
