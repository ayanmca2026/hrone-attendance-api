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


def test_overnight_shift_overtime_boundaries(client):
    # Overnight shift: 22:00 to 06:00
    client.post("/employees", json={
        "emp_code": "EMP0015", "name": "OT Bound", "email": "ot@bound.com", "department": "Support",
        "shift_start": "22:00", "shift_end": "06:00", "joined_on": "2026-01-01"
    })

    # Punch in 2026-01-01 22:00:00 IST -> 1767285000000. Shift end is 2026-01-02 06:00:00 IST -> 1767313800000.
    client.post("/attendance/punch-in", json={"emp_code": "EMP0015", "punched_at": 1767285000000})

    # Punch out at 06:29:00 IST (29 minutes overtime -> below 30 threshold -> overtime_minutes = 0)
    resp_29 = client.post("/attendance/punch-out", json={"emp_code": "EMP0015", "punched_at": 1767315540000})
    assert resp_29.status_code == 200
    assert resp_29.json()["overtime_minutes"] == 0

    # Next night punch in: 2026-01-02 22:00:00 IST -> 1767371400000
    client.post("/attendance/punch-in", json={"emp_code": "EMP0015", "punched_at": 1767371400000})

    # Punch out at 06:30:00 IST next day (exactly 30 minutes overtime -> overtime_minutes = 30)
    # 2026-01-03 06:30:00 IST -> 1767402000000
    resp_30 = client.post("/attendance/punch-out", json={"emp_code": "EMP0015", "punched_at": 1767402000000})
    assert resp_30.status_code == 200
    assert resp_30.json()["overtime_minutes"] == 30


def test_invalid_timestamps_and_calendar_dates(client):
    client.post("/employees", json={
        "emp_code": "EMP0016", "name": "Val Test", "email": "val@test.com", "department": "Eng",
        "joined_on": "2026-01-01", "shift_start": "09:30", "shift_end": "18:30"
    })

    # Timestamp below MS_MIN (looks like seconds, not ms)
    r_low = client.post("/attendance/punch-in", json={"emp_code": "EMP0016", "punched_at": 1767240000})
    assert r_low.status_code == 422

    # Timestamp above MS_MAX
    r_high = client.post("/attendance/punch-in", json={"emp_code": "EMP0016", "punched_at": 5000000000000})
    assert r_high.status_code == 422

    # Invalid attendance list date_from
    r_date1 = client.get("/attendance?date_from=invalid-date")
    assert r_date1.status_code == 422

    # Invalid attendance list date_to
    r_date2 = client.get("/attendance?date_to=invalid-date")
    assert r_date2.status_code == 422

    # date_from > date_to
    r_range = client.get("/attendance?date_from=2026-01-15&date_to=2026-01-05")
    assert r_range.status_code == 422


def test_concurrent_duplicate_punch_in(client):
    from concurrent.futures import ThreadPoolExecutor

    client.post("/employees", json={
        "emp_code": "EMP0017", "name": "Race Emp", "email": "race@test.com", "department": "Eng",
        "joined_on": "2026-01-01", "shift_start": "09:30", "shift_end": "18:30"
    })

    def do_punch():
        return client.post("/attendance/punch-in", json={"emp_code": "EMP0017", "punched_at": 1767240000000})

    with ThreadPoolExecutor(max_workers=5) as executor:
        responses = list(executor.map(lambda _: do_punch(), range(5)))

    statuses = [r.status_code for r in responses]
    assert statuses.count(201) == 1
    assert statuses.count(409) == 4


def test_concurrent_duplicate_punch_out(client):
    from concurrent.futures import ThreadPoolExecutor

    client.post("/employees", json={
        "emp_code": "EMP0018", "name": "Race Out", "email": "raceout@test.com", "department": "Eng",
        "joined_on": "2026-01-01", "shift_start": "09:30", "shift_end": "18:30"
    })
    client.post("/attendance/punch-in", json={"emp_code": "EMP0018", "punched_at": 1767240000000})

    def do_punch_out():
        return client.post("/attendance/punch-out", json={"emp_code": "EMP0018", "punched_at": 1767272400000})

    with ThreadPoolExecutor(max_workers=5) as executor:
        responses = list(executor.map(lambda _: do_punch_out(), range(5)))

    statuses = [r.status_code for r in responses]
    assert statuses.count(200) == 1
    assert statuses.count(409) == 4


def test_earlier_attendance_record_remains_open(client):
    client.post("/employees", json={
        "emp_code": "EMP0019", "name": "Open Record Emp", "email": "open@test.com", "department": "Eng",
        "joined_on": "2026-01-01", "shift_start": "09:30", "shift_end": "18:30"
    })

    # Day 1: 2026-01-01 punch in, never punch out
    r1 = client.post("/attendance/punch-in", json={"emp_code": "EMP0019", "punched_at": 1767240000000})
    assert r1.status_code == 201

    # Day 2: 2026-01-02 punch in
    # 2026-01-02 09:30:00 IST -> 1767326400000
    r2 = client.post("/attendance/punch-in", json={"emp_code": "EMP0019", "punched_at": 1767326400000})
    assert r2.status_code == 201

    # Day 2 punch out (closes Day 2 record, leaving Day 1 open)
    # 2026-01-02 18:30:00 IST -> 1767358800000
    r_out = client.post("/attendance/punch-out", json={"emp_code": "EMP0019", "punched_at": 1767358800000})
    assert r_out.status_code == 200
    assert r_out.json()["date"] == "2026-01-02"
    assert r_out.json()["work_hours"] == 9.0

    # Verify both records via GET /attendance
    list_resp = client.get("/attendance?emp_code=EMP0019")
    assert list_resp.status_code == 200
    records = list_resp.json()["items"]
    assert len(records) == 2
    # Records are sorted by date descending: records[0] is Day 2, records[1] is Day 1
    day2 = next(r for r in records if r["date"] == "2026-01-02")
    day1 = next(r for r in records if r["date"] == "2026-01-01")
    assert day2["punch_out"] is not None
    assert day1["punch_out"] is None

    # Immediate next punch out attempt for Day 2 timestamp returns 409 (already punched out)
    r_dup = client.post("/attendance/punch-out", json={"emp_code": "EMP0019", "punched_at": 1767358800000})
    assert r_dup.status_code == 409


