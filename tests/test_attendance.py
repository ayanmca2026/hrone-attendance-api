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


def test_punch_out_overtime_and_half_day(client):
    client.post("/employees", json={
        "emp_code": "EMP0002", "name": "B", "email": "b@b.com", "department": "Eng", "joined_on": "2026-01-01",
        "shift_start": "09:30", "shift_end": "18:30"
    })
    # Punch in 09:30 IST
    client.post("/attendance/punch-in", json={"emp_code": "EMP0002", "punched_at": 1767240000000})

    # Punch out at 13:30 IST (4 hours work -> half_day = True)
    resp = client.post("/attendance/punch-out", json={"emp_code": "EMP0002", "punched_at": 1767254400000})
    assert resp.status_code == 200
    assert resp.json()["work_hours"] == 4.0
    assert resp.json()["half_day"] is True
    assert resp.json()["overtime_minutes"] == 0


def test_overnight_shift(client):
    # Overnight shift: 22:00 to 06:00
    client.post("/employees", json={
        "emp_code": "EMP0003", "name": "Night Owl", "email": "night@example.com", "department": "Support",
        "shift_start": "22:00", "shift_end": "06:00", "joined_on": "2026-01-01"
    })
    # Punch in 2026-01-02 01:00:00 IST -> belongs to attendance date 2026-01-01
    resp_in = client.post("/attendance/punch-in", json={"emp_code": "EMP0003", "punched_at": 1767295800000})
    assert resp_in.status_code == 201
    assert resp_in.json()["date"] == "2026-01-01"

    # Punch out 2026-01-02 06:45:00 IST (45 mins past 06:00 shift_end)
    resp_out = client.post("/attendance/punch-out", json={"emp_code": "EMP0003", "punched_at": 1767316500000})
    assert resp_out.status_code == 200
    assert resp_out.json()["overtime_minutes"] == 45


def test_punch_out_invalid_duration(client):
    client.post("/employees", json={
        "emp_code": "EMP0004", "name": "D", "email": "d@d.com", "department": "Eng", "joined_on": "2026-01-01",
        "shift_start": "09:30", "shift_end": "18:30"
    })
    client.post("/attendance/punch-in", json={"emp_code": "EMP0004", "punched_at": 1767240000000})

    # Punch out earlier than punch in (no punch-in found at or before punched_at) returns 404
    resp_earlier = client.post("/attendance/punch-out", json={"emp_code": "EMP0004", "punched_at": 1767239000000})
    assert resp_earlier.status_code == 404

    # Punch out exactly equal to punch in (duration == 0) returns 422
    resp_equal = client.post("/attendance/punch-out", json={"emp_code": "EMP0004", "punched_at": 1767240000000})
    assert resp_equal.status_code == 422

    # Punch out > 24 hours returns 422
    resp_late = client.post("/attendance/punch-out", json={"emp_code": "EMP0004", "punched_at": 1767240000000 + 86500 * 1000})
    assert resp_late.status_code == 422


def test_list_attendance(client):
    client.post("/employees", json={
        "emp_code": "EMP0005", "name": "E", "email": "e@e.com", "department": "Eng", "joined_on": "2026-01-01",
        "shift_start": "09:30", "shift_end": "18:30"
    })
    client.post("/attendance/punch-in", json={"emp_code": "EMP0005", "punched_at": 1767240000000})

    resp = client.get("/attendance?emp_code=EMP0005&date_from=2026-01-01&date_to=2026-01-01")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["emp_code"] == "EMP0005"

