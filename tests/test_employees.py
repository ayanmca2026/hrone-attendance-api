def test_create_employee(client):
    payload = {
        "emp_code": "EMP0001",
        "name": "Test Emp",
        "email": "test@example.com",
        "department": "Engineering",
        "shift_start": "09:30",
        "shift_end": "18:30",
        "joined_on": "2026-01-01"
    }
    response = client.post("/employees", json=payload)
    assert response.status_code == 201
    assert "created_at" in response.json()
    assert response.json()["emp_code"] == "EMP0001"

    # Duplicate
    response2 = client.post("/employees", json=payload)
    assert response2.status_code == 409

def test_create_employee_invalid(client):
    payload = {
        "emp_code": "EMP0001",
        "name": "Test Emp",
        "email": "invalid-email",
        "department": "Engineering",
        "shift_start": "09:30",
        "shift_end": "09:30", # Same as start
        "joined_on": "2026-01-01"
    }
    response = client.post("/employees", json=payload)
    assert response.status_code == 422

def test_list_employees(client):
    for i in range(5):
        client.post("/employees", json={
            "emp_code": f"EMP000{i}",
            "name": f"Test Emp {i}",
            "email": f"test{i}@example.com",
            "department": "Engineering" if i % 2 == 0 else "Sales",
            "shift_start": "09:30",
            "shift_end": "18:30",
            "joined_on": "2026-01-01"
        })
    
    resp = client.get("/employees?page=1&page_size=2")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2
    assert resp.json()["total"] == 5

    resp = client.get("/employees?department=Sales")
    assert len(resp.json()["items"]) == 2
    assert resp.json()["total"] == 2
