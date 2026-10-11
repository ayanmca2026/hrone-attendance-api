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

