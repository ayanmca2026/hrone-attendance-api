import pytest
from app.main import db
from sample_seed import seed_sample_data


def test_seed_safe_upsert_preserves_unrelated_data():
    # Insert existing unrelated records into test database
    db.employees.insert_one({
        "emp_code": "EMP9999",
        "name": "Custom Unrelated User",
        "email": "custom@example.com",
        "department": "CustomDept",
        "shift_start": "09:30",
        "shift_end": "18:30",
        "joined_on": "2026-01-01"
    })
    db.attendance_logs.insert_one({
        "emp_code": "EMP9999",
        "date": "2026-01-05",
        "status": "PRESENT",
        "punch_in": None,
        "punch_out": None,
        "history": []
    })

    # Run default safe seeding (reset=False)
    counts = seed_sample_data(target_db=db, reset=False)
    assert counts["employees"] > 0
    assert counts["attendance_logs"] > 0

    # Verify that the unrelated employee and attendance log were NOT deleted
    assert db.employees.find_one({"emp_code": "EMP9999"}) is not None
    assert db.attendance_logs.find_one({"emp_code": "EMP9999", "date": "2026-01-05"}) is not None

    # Verify idempotency by running again
    counts2 = seed_sample_data(target_db=db, reset=False)
    assert counts2["employees"] == counts["employees"]
    assert db.employees.find_one({"emp_code": "EMP9999"}) is not None


def test_seed_safety_guard_blocks_real_db(monkeypatch):
    class MockDb:
        name = "hrone_production"
        employees = None
        attendance_logs = None

        def __getitem__(self, item):
            return self

    mock_db = MockDb()
    monkeypatch.delenv("CONFIRM_RESET_DATABASE", raising=False)

    with pytest.raises(RuntimeError, match="SAFETY GUARD: Refusing to delete data in non-disposable database"):
        seed_sample_data(target_db=mock_db, reset=True)
