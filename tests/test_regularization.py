def test_regularize_attendance(client):
    client.post("/employees", json={
        "emp_code": "EMP0001", "name": "A", "email": "a@a.com", "department": "Eng", "joined_on": "2026-01-01",
        "shift_start": "09:30", "shift_end": "18:30"
    })
    client.post("/attendance/punch-in", json={"emp_code": "EMP0001", "punched_at": 1767240000000}) # 09:30 IST

    # Regularize: Set punch_in to 09:40:01 IST (1767240601000)
    resp = client.patch("/attendance/EMP0001/2026-01-01", json={
        "punch_in": 1767240601000,
        "reason": "Fixing punch",
        "regularized_by": "HR"
    })
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["late_minutes"] == 10
    assert len(data["history"]) == 1
    assert data["history"][0]["changes"]["punch_in"]["from"] == 1767240000000
    assert data["history"][0]["changes"]["punch_in"]["to"] == 1767240601000

def test_regularize_absent(client):
    client.post("/employees", json={
        "emp_code": "EMP0001", "name": "A", "email": "a@a.com", "department": "Eng", "joined_on": "2026-01-01",
        "shift_start": "09:30", "shift_end": "18:30"
    })
    client.post("/attendance/punch-in", json={"emp_code": "EMP0001", "punched_at": 1767240000000}) # 09:30 IST
    
    # Change status to ABSENT
    resp = client.patch("/attendance/EMP0001/2026-01-01", json={
        "status": "ABSENT",
        "reason": "Absent marked",
        "regularized_by": "HR"
    })
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["punch_in"] is None
    assert data["punch_out"] is None
    assert data["late_minutes"] == 0
    assert len(data["history"]) == 1
    assert "status" in data["history"][0]["changes"]


def test_regularize_errors(client):
    client.post("/employees", json={
        "emp_code": "EMP0001", "name": "A", "email": "a@a.com", "department": "Eng", "joined_on": "2026-01-01",
        "shift_start": "09:30", "shift_end": "18:30"
    })
    client.post("/attendance/punch-in", json={"emp_code": "EMP0001", "punched_at": 1767240000000})

    # Unknown employee -> 404
    resp = client.patch("/attendance/EMP9999/2026-01-01", json={"status": "WFH", "reason": "Home office", "regularized_by": "HR"})
    assert resp.status_code == 404

    # Unknown date -> 404
    resp = client.patch("/attendance/EMP0001/2026-01-02", json={"status": "WFH", "reason": "Home office", "regularized_by": "HR"})
    assert resp.status_code == 404

    # No changes detected -> 422
    resp = client.patch("/attendance/EMP0001/2026-01-01", json={"status": "PRESENT", "reason": "No changes made", "regularized_by": "HR"})
    assert resp.status_code == 422

    # punch_in supplied with ABSENT -> 422
    resp = client.patch("/attendance/EMP0001/2026-01-01", json={"status": "ABSENT", "punch_in": 1767240000000, "reason": "Invalid absent", "regularized_by": "HR"})
    assert resp.status_code == 422


def test_regularize_partial_updates(client):
    client.post("/employees", json={
        "emp_code": "EMP0008", "name": "Partial Reg", "email": "part@test.com", "department": "Eng",
        "joined_on": "2026-01-01", "shift_start": "09:30", "shift_end": "18:30"
    })
    # Punch in 09:30 IST (1767240000000)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0008", "punched_at": 1767240000000})

    # Partial update 1: Set ONLY punch_out (18:30 IST -> 1767272400000)
    r1 = client.patch("/attendance/EMP0008/2026-01-01", json={
        "punch_out": 1767272400000,
        "reason": "Punch-out regularization",
        "regularized_by": "HR.Admin"
    })
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["punch_in"] == 1767240000000  # punch_in unchanged
    assert d1["punch_out"] == 1767272400000
    assert d1["work_hours"] == 9.0
    assert d1["status"] == "PRESENT"  # status unchanged
    assert len(d1["history"]) == 1

    # Partial update 2: Set ONLY status to WFH
    r2 = client.patch("/attendance/EMP0008/2026-01-01", json={
        "status": "WFH",
        "reason": "Worked from home approved",
        "regularized_by": "Manager.Bob"
    })
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["status"] == "WFH"
    assert d2["punch_in"] == 1767240000000  # punch_in still preserved
    assert d2["punch_out"] == 1767272400000  # punch_out still preserved
    assert len(d2["history"]) == 2

    # Partial update 3: Set ONLY punch_in to 09:45:00 IST (1767240900000 -> 15 min late)
    r3 = client.patch("/attendance/EMP0008/2026-01-01", json={
        "punch_in": 1767240900000,
        "reason": "Adjusted punch in time",
        "regularized_by": "HR.Lead"
    })
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["late_minutes"] == 15
    assert d3["work_hours"] == 8.75  # recomputed work_hours: (18:30 - 09:45 = 8.75h)
    assert len(d3["history"]) == 3


def test_regularize_absent_leave_transitions_and_history_chain(client):
    client.post("/employees", json={
        "emp_code": "EMP0009", "name": "Audit Chain", "email": "chain@test.com", "department": "Eng",
        "joined_on": "2026-01-01", "shift_start": "09:30", "shift_end": "18:30"
    })
    client.post("/attendance/punch-in", json={"emp_code": "EMP0009", "punched_at": 1767240000000})

    # Step 1: Transition PRESENT -> ABSENT
    r1 = client.patch("/attendance/EMP0009/2026-01-01", json={
        "status": "ABSENT",
        "reason": "Marked unapproved absence",
        "regularized_by": "HR.Supervisor"
    })
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["status"] == "ABSENT"
    assert d1["punch_in"] is None
    assert d1["punch_out"] is None
    assert d1["late_minutes"] == 0
    assert len(d1["history"]) == 1
    assert d1["history"][0]["reason"] == "Marked unapproved absence"

    # Step 2: Transition ABSENT -> LEAVE
    r2 = client.patch("/attendance/EMP0009/2026-01-01", json={
        "status": "LEAVE",
        "reason": "Converted to approved leave",
        "regularized_by": "HR.Manager"
    })
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["status"] == "LEAVE"
    assert len(d2["history"]) == 2
    # Ensure history preserves both previous and current entries
    assert d2["history"][0]["reason"] == "Marked unapproved absence"
    assert d2["history"][1]["reason"] == "Converted to approved leave"

    # Step 3: Transition LEAVE -> PRESENT with explicit punch_in and punch_out
    r3 = client.patch("/attendance/EMP0009/2026-01-01", json={
        "status": "PRESENT",
        "punch_in": 1767240000000,
        "punch_out": 1767272400000,
        "reason": "Leave cancelled, employee was present",
        "regularized_by": "HR.Director"
    })
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["status"] == "PRESENT"
    assert d3["punch_in"] == 1767240000000
    assert d3["work_hours"] == 9.0
    assert len(d3["history"]) == 3
    assert d3["history"][2]["reason"] == "Leave cancelled, employee was present"


def test_regularize_invalid_dates_and_boundaries(client):
    client.post("/employees", json={
        "emp_code": "EMP0010", "name": "Boundary Val", "email": "bv@test.com", "department": "Eng",
        "joined_on": "2026-01-01", "shift_start": "09:30", "shift_end": "18:30"
    })
    client.post("/attendance/punch-in", json={"emp_code": "EMP0010", "punched_at": 1767240000000})

    # Invalid path date format
    r_bad_path = client.patch("/attendance/EMP0010/invalid-date", json={
        "status": "WFH", "reason": "Bad date format", "regularized_by": "HR"
    })
    assert r_bad_path.status_code == 422

    # punch_in shifting attendance date to a different day (e.g. 2026-01-02 09:30 IST)
    r_diff_date = client.patch("/attendance/EMP0010/2026-01-01", json={
        "punch_in": 1767326400000,
        "reason": "Shifting date",
        "regularized_by": "HR"
    })
    assert r_diff_date.status_code == 422

    # punch_out earlier than punch_in
    r_earlier = client.patch("/attendance/EMP0010/2026-01-01", json={
        "punch_in": 1767240000000,
        "punch_out": 1767230000000,
        "reason": "Out before in",
        "regularized_by": "HR"
    })
    assert r_earlier.status_code == 422

    # punch_out > 24 hours after punch_in
    r_toolong = client.patch("/attendance/EMP0010/2026-01-01", json={
        "punch_in": 1767240000000,
        "punch_out": 1767240000000 + 86500 * 1000,
        "reason": "Too long",
        "regularized_by": "HR"
    })
    assert r_toolong.status_code == 422


