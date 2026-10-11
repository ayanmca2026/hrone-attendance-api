from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError
from app.main import db


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
    data = response.json()
    assert "created_at" in data
    assert isinstance(data["created_at"], int)
    assert data["emp_code"] == "EMP0001"
    assert data["name"] == "Test Emp"
    assert data["email"] == "test@example.com"
    assert data["department"] == "Engineering"
    assert data["shift_start"] == "09:30"
    assert data["shift_end"] == "18:30"
    assert data["joined_on"] == "2026-01-01"

    # Duplicate with same payload returns 409
    response2 = client.post("/employees", json=payload)
    assert response2.status_code == 409
    assert response2.json() == {"detail": "emp_code already exists"}

    # Duplicate with different payload but same emp_code returns 409
    different_payload = dict(payload, name="Another Name", email="another@example.com")
    response3 = client.post("/employees", json=different_payload)
    assert response3.status_code == 409
    assert response3.json() == {"detail": "emp_code already exists"}


def test_create_employee_and_retrieve_via_get(client):
    payload = {
        "emp_code": "EMP5001",
        "name": "Retrievable Employee",
        "email": "retrievable@example.com",
        "department": "Engineering",
        "shift_start": "09:30",
        "shift_end": "18:30",
        "joined_on": "2026-05-10"
    }
    create_resp = client.post("/employees", json=payload)
    assert create_resp.status_code == 201
    created_data = create_resp.json()

    # Retrieve through GET /employees
    get_resp = client.get("/employees")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["total"] >= 1
    found = [item for item in get_data["items"] if item["emp_code"] == "EMP5001"]
    assert len(found) == 1
    retrieved = found[0]
    assert retrieved["emp_code"] == "EMP5001"
    assert retrieved["name"] == "Retrievable Employee"
    assert retrieved["email"] == "retrievable@example.com"
    assert retrieved["department"] == "Engineering"
    assert retrieved["created_at"] == created_data["created_at"]

    # Filter by department
    dept_resp = client.get("/employees?department=Engineering")
    assert dept_resp.status_code == 200
    assert any(item["emp_code"] == "EMP5001" for item in dept_resp.json()["items"])


def test_create_employee_invalid_email(client):
    base_payload = {
        "emp_code": "EMP6001",
        "name": "Invalid Email Emp",
        "department": "QA",
        "joined_on": "2026-01-01"
    }
    invalid_emails = [
        "invalid-email",
        "plainaddress",
        "@missingusername.com",
        "username@.com",
        "username@com",
        "user name@example.com",
        ""
    ]
    for email in invalid_emails:
        payload = dict(base_payload, email=email)
        response = client.post("/employees", json=payload)
        assert response.status_code == 422, f"Expected 422 for email: '{email}'"


def test_create_employee_invalid_date(client):
    base_payload = {
        "emp_code": "EMP6002",
        "name": "Invalid Date Emp",
        "email": "date.test@example.com",
        "department": "QA"
    }
    invalid_dates = [
        "not-a-date",
        "2026-02-31",      # Invalid day for February
        "2026-13-01",      # Invalid month
        "2026-00-10",      # Invalid month 00
        "2026/01/01",      # Wrong delimiter
        "01-01-2026",      # Wrong order
        ""
    ]
    for date_val in invalid_dates:
        payload = dict(base_payload, joined_on=date_val)
        response = client.post("/employees", json=payload)
        assert response.status_code == 422, f"Expected 422 for date: '{date_val}'"


def test_create_employee_invalid_shift_and_code(client):
    base = {
        "emp_code": "EMP6003",
        "name": "Shift Test",
        "email": "shift@example.com",
        "department": "QA",
        "joined_on": "2026-01-01"
    }

    # Shift start identical to shift end
    resp = client.post("/employees", json=dict(base, shift_start="09:30", shift_end="09:30"))
    assert resp.status_code == 422

    # Invalid shift time format
    resp = client.post("/employees", json=dict(base, shift_start="25:00", shift_end="18:30"))
    assert resp.status_code == 422

    # Invalid emp_code format (must be EMP followed by 4-6 digits)
    invalid_codes = ["EMP1", "EMP12", "EMP123", "EMPLOYEE1", "12345", "emp0001", ""]
    for code in invalid_codes:
        resp = client.post("/employees", json=dict(base, emp_code=code))
        assert resp.status_code == 422, f"Expected 422 for emp_code: '{code}'"


def test_create_employee_duplicate_race_mock(client):
    payload = {
        "emp_code": "EMP7001",
        "name": "Race Emp",
        "email": "race@example.com",
        "department": "QA",
        "joined_on": "2026-01-01"
    }
    # Simulate race condition where MongoDB raises DuplicateKeyError on insert_one
    with patch.object(Collection, "insert_one", side_effect=DuplicateKeyError("E11000 duplicate key error")):
        response = client.post("/employees", json=payload)
        assert response.status_code == 409
        assert response.json() == {"detail": "emp_code already exists"}


def test_create_employee_concurrent_race(client):
    payload = {
        "emp_code": "EMP8001",
        "name": "Concurrent Emp",
        "email": "concurrent@example.com",
        "department": "QA",
        "joined_on": "2026-01-01"
    }

    # Fire multiple concurrent requests trying to create the same employee
    def send_create():
        return client.post("/employees", json=payload)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(send_create) for _ in range(5)]
        responses = [f.result() for f in futures]

    statuses = [r.status_code for r in responses]
    assert 201 in statuses, "At least one request should succeed with 201"
    assert statuses.count(201) == 1, "Exactly one request must succeed with 201"
    for r in responses:
        if r.status_code != 201:
            assert r.status_code == 409
            assert r.json() == {"detail": "emp_code already exists"}

    # No unhandled 500 error
    assert 500 not in statuses

    # Exactly one record in database
    count = db.employees.count_documents({"emp_code": "EMP8001"})
    assert count == 1


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

