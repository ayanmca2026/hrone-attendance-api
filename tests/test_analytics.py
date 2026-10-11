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
    assert items[0]["avg_work_hours"] is None

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
    # Day 1: 2026-01-01 (Thu, working day with 0 records -> rate 0.0, moving_avg 0.0)
    assert items[0]["date"] == "2026-01-01"
    assert items[0]["headcount"] == 1
    assert items[0]["is_working_day"] is True
    assert items[0]["attendance_rate"] == 0.0
    assert items[0]["moving_avg_7d"] == 0.0

    # Day 3: 2026-01-03 (Sat, non-working day -> rate None, moving_avg 0.0 from preceding 0.0s)
    assert items[2]["date"] == "2026-01-03"
    assert items[2]["is_working_day"] is False
    assert items[2]["attendance_rate"] is None
    assert items[2]["moving_avg_7d"] == 0.0


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


def test_department_summary_avg_work_hours_short_sessions_and_nulls(client):
    """Edge Case A:
    Verify department summary average work hours calculation:
    - EMP0031: 9.00 work hours (PRESENCE_STATUS, punch-in and punch-out)
    - EMP0032: 0.02 work hours short session (72 seconds session, PRESENCE_STATUS)
    - EMP0033: punch-in only (work_hours is null, PRESENCE_STATUS) -> excluded from avg
    - EMP0034: regularized to ABSENT (work_hours is null, non-presence) -> excluded from avg
    QA department average: (9.00 + 0.02) / 2 = 4.51 hours.
    No arbitrary minimum-hours threshold is applied.
    """
    for code, name, email in [
        ("EMP0031", "QA One", "qa1@test.com"),
        ("EMP0032", "QA Two", "qa2@test.com"),
        ("EMP0033", "QA Three", "qa3@test.com"),
        ("EMP0034", "QA Four", "qa4@test.com"),
    ]:
        client.post("/employees", json={
            "emp_code": code, "name": name, "email": email, "department": "QA",
            "joined_on": "2026-01-01", "shift_start": "09:30", "shift_end": "18:30"
        })

    # EMP0031: 9.00 work hours (09:30:00 to 18:30:00 IST -> 1767240000000 to 1767272400000)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0031", "punched_at": 1767240000000})
    client.post("/attendance/punch-out", json={"emp_code": "EMP0031", "punched_at": 1767272400000})

    # EMP0032: 0.02 work hours short session (09:30:00 to 09:31:12 IST -> 72s = 0.02h)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0032", "punched_at": 1767240000000})
    client.post("/attendance/punch-out", json={"emp_code": "EMP0032", "punched_at": 1767240072000})

    # EMP0033: Punched in but no punch-out (work_hours is null)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0033", "punched_at": 1767240000000})

    # EMP0034: Punched in then regularized to ABSENT (work_hours is null, non-presence)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0034", "punched_at": 1767240000000})
    client.patch("/attendance/EMP0034/2026-01-01", json={
        "status": "ABSENT",
        "reason": "Unapproved absence",
        "regularized_by": "HR"
    })

    resp = client.get("/analytics/departments/summary?month=2026-01&department=QA")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    dept = items[0]
    assert dept["department"] == "QA"
    assert dept["headcount"] == 4
    # Expected avg_work_hours: (9.00 + 0.02) / 2 = 4.51
    assert dept["avg_work_hours"] == 4.51


def test_department_summary_all_null_work_hours(client):
    """Edge Case A:
    When department records only have null work hours (e.g. punch-in without punch-out),
    avg_work_hours must be null.
    """
    client.post("/employees", json={
        "emp_code": "EMP0041", "name": "Null Worker", "email": "null@test.com", "department": "DevOps",
        "joined_on": "2026-01-01", "shift_start": "09:30", "shift_end": "18:30"
    })
    # Punch in only, no punch out
    client.post("/attendance/punch-in", json={"emp_code": "EMP0041", "punched_at": 1767240000000})

    resp = client.get("/analytics/departments/summary?month=2026-01&department=DevOps")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["avg_work_hours"] is None


def test_department_trend_weekend_half_day_and_moving_average(client):
    """Edge Case B:
    Verify department trend and 7-calendar-day moving average semantics:
    - Weekend attendance: present_count includes weekend records (e.g. Saturday)
    - Half-day attendance: work_hours < 4.50 counts as 0.5 present_count
    - Non-working-day null rates: attendance_rate is null on non-working days (weekends)
    - Moving average window: 7 calendar days; MongoDB $avg ignores null attendance_rate values
    """
    client.post("/employees", json={
        "emp_code": "EMP0051", "name": "Ops Lead", "email": "ops@test.com", "department": "Ops",
        "joined_on": "2026-01-01", "shift_start": "09:30", "shift_end": "18:30"
    })

    # Day 1: 2026-01-01 (Thursday, is_working_day=True) -> Full day (9.00h)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0051", "punched_at": 1767240000000})
    client.post("/attendance/punch-out", json={"emp_code": "EMP0051", "punched_at": 1767272400000})

    # Day 2: 2026-01-02 (Friday, is_working_day=True) -> Half day (3.50h: 09:30 to 13:00)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0051", "punched_at": 1767326400000})
    client.post("/attendance/punch-out", json={"emp_code": "EMP0051", "punched_at": 1767339000000})

    # Day 3: 2026-01-03 (Saturday, is_working_day=False) -> Weekend attendance: 4.00h (half_day=True)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0051", "punched_at": 1767414600000})
    client.post("/attendance/punch-out", json={"emp_code": "EMP0051", "punched_at": 1767429000000})

    # Day 4: 2026-01-04 (Sunday, is_working_day=False) -> No punch

    # Day 5: 2026-01-05 (Monday, is_working_day=True) -> Full day (9.00h)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0051", "punched_at": 1767585600000})
    client.post("/attendance/punch-out", json={"emp_code": "EMP0051", "punched_at": 1767618000000})

    # Day 6: 2026-01-06 (Tuesday, is_working_day=True) -> No punch (absent / no record, rate 0.0)

    # Day 7: 2026-01-07 (Wednesday, is_working_day=True) -> Full day (9.00h)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0051", "punched_at": 1767758400000})
    client.post("/attendance/punch-out", json={"emp_code": "EMP0051", "punched_at": 1767790800000})

    # Day 8: 2026-01-08 (Thursday, is_working_day=True) -> Full day (9.00h)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0051", "punched_at": 1767844800000})
    client.post("/attendance/punch-out", json={"emp_code": "EMP0051", "punched_at": 1767877200000})

    resp = client.get("/analytics/departments/Ops/trend?from=2026-01-01&to=2026-01-08")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 8

    # Day 1: 2026-01-01 (Thu)
    assert items[0]["date"] == "2026-01-01"
    assert items[0]["is_working_day"] is True
    assert items[0]["headcount"] == 1
    assert items[0]["present_count"] == 1.0
    assert items[0]["attendance_rate"] == 1.0000
    assert items[0]["moving_avg_7d"] == 1.0000

    # Day 2: 2026-01-02 (Fri) - half-day attendance (0.5)
    assert items[1]["date"] == "2026-01-02"
    assert items[1]["is_working_day"] is True
    assert items[1]["headcount"] == 1
    assert items[1]["present_count"] == 0.5
    assert items[1]["attendance_rate"] == 0.5000
    assert items[1]["moving_avg_7d"] == 0.7500  # (1.0 + 0.5) / 2

    # Day 3: 2026-01-03 (Sat) - weekend attendance reported in present_count, rate is null
    assert items[2]["date"] == "2026-01-03"
    assert items[2]["is_working_day"] is False
    assert items[2]["headcount"] == 1
    assert items[2]["present_count"] == 0.5
    assert items[2]["attendance_rate"] is None
    assert items[2]["moving_avg_7d"] == 0.7500  # $avg ignores null weekend rate

    # Day 4: 2026-01-04 (Sun) - non-working day, no punch, rate is null
    assert items[3]["date"] == "2026-01-04"
    assert items[3]["is_working_day"] is False
    assert items[3]["headcount"] == 1
    assert items[3]["present_count"] == 0.0
    assert items[3]["attendance_rate"] is None
    assert items[3]["moving_avg_7d"] == 0.7500  # $avg ignores null weekend rate

    # Day 5: 2026-01-05 (Mon) - working day, full day
    assert items[4]["date"] == "2026-01-05"
    assert items[4]["is_working_day"] is True
    assert items[4]["headcount"] == 1
    assert items[4]["present_count"] == 1.0
    assert items[4]["attendance_rate"] == 1.0000
    assert items[4]["moving_avg_7d"] == 0.8333  # (1.0 + 0.5 + 1.0) / 3 = 0.8333

    # Day 6: 2026-01-06 (Tue) - working day, no punch -> rate is 0.0
    assert items[5]["date"] == "2026-01-06"
    assert items[5]["is_working_day"] is True
    assert items[5]["headcount"] == 1
    assert items[5]["present_count"] == 0.0
    assert items[5]["attendance_rate"] == 0.0000
    assert items[5]["moving_avg_7d"] == 0.6250  # (1.0 + 0.5 + 1.0 + 0.0) / 4 = 0.6250

    # Day 7: 2026-01-07 (Wed) - working day, full day
    assert items[6]["date"] == "2026-01-07"
    assert items[6]["is_working_day"] is True
    assert items[6]["headcount"] == 1
    assert items[6]["present_count"] == 1.0
    assert items[6]["attendance_rate"] == 1.0000
    assert items[6]["moving_avg_7d"] == 0.7000  # (1.0 + 0.5 + 1.0 + 0.0 + 1.0) / 5 = 0.7000

    # Day 8: 2026-01-08 (Thu) - 7-day document window [-6, 0] covers Day 2 through Day 8 (Day 1 dropped)
    assert items[7]["date"] == "2026-01-08"
    assert items[7]["is_working_day"] is True
    assert items[7]["headcount"] == 1
    assert items[7]["present_count"] == 1.0
    assert items[7]["attendance_rate"] == 1.0000
    # Window has Day 2 (0.5), Day 3 (null), Day 4 (null), Day 5 (1.0), Day 6 (0.0), Day 7 (1.0), Day 8 (1.0)
    # Non-null values: 0.5, 1.0, 0.0, 1.0, 1.0 (5 values, sum = 3.5) -> 3.5 / 5 = 0.7000
    assert items[7]["moving_avg_7d"] == 0.7000


def test_leaderboard_competition_ranking_and_limit(client):
    """
    Standard competition ranking with ties (1, 2, 2, 4).
    The specification states:
    `limit applies after ranking: return every employee whose rank <= limit.
    The response can therefore contain more than limit rows when employees tie at a rank <= limit.`
    """
    client.post("/employees", json={"emp_code": "EMP0061", "name": "L1", "email": "l1@test.com", "department": "Eng", "joined_on": "2026-01-01"})
    client.post("/employees", json={"emp_code": "EMP0062", "name": "L2", "email": "l2@test.com", "department": "Eng", "joined_on": "2026-01-01"})
    client.post("/employees", json={"emp_code": "EMP0063", "name": "L3", "email": "l3@test.com", "department": "Eng", "joined_on": "2026-01-01"})
    client.post("/employees", json={"emp_code": "EMP0064", "name": "L4", "email": "l4@test.com", "department": "Eng", "joined_on": "2026-01-01"})

    # EMP0061: late by 50 mins (09:30 shift, in at 10:20:00 -> 1767243000000)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0061", "punched_at": 1767243000000})

    # EMP0062: late by 30 mins (09:30 shift, in at 10:00:00 -> 1767241800000)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0062", "punched_at": 1767241800000})

    # EMP0063: late by 30 mins (09:30 shift, in at 10:00:00 -> 1767241800000)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0063", "punched_at": 1767241800000})

    # EMP0064: late by 15 mins (09:30 shift, in at 09:45:00 -> 1767240900000)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0064", "punched_at": 1767240900000})

    # Query with limit=2:
    # EMP0061 has rank 1.
    # EMP0062 & EMP0063 have rank 2 (tied).
    # EMP0064 has rank 4.
    # Since rank <= 2, all 3 employees (EMP0061, EMP0062, EMP0063) must be returned!
    # Even though limit=2, more than 2 rows are returned due to the tie!
    resp = client.get("/analytics/leaderboard/late?month=2026-01&limit=2")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 3
    assert items[0]["emp_code"] == "EMP0061"
    assert items[0]["rank"] == 1
    assert items[1]["emp_code"] == "EMP0062"
    assert items[1]["rank"] == 2
    assert items[2]["emp_code"] == "EMP0063"
    assert items[2]["rank"] == 2

    # Query with limit=3:
    # Ranks are 1, 2, 2, 4. Ranks <= 3 are 1, 2, 2. Rank 4 is excluded.
    resp3 = client.get("/analytics/leaderboard/late?month=2026-01&limit=3")
    assert resp3.status_code == 200
    items3 = resp3.json()["items"]
    assert len(items3) == 3
    assert [i["rank"] for i in items3] == [1, 2, 2]

    # Query with limit=4: all 4 are returned
    resp4 = client.get("/analytics/leaderboard/late?month=2026-01&limit=4")
    assert resp4.status_code == 200
    assert len(resp4.json()["items"]) == 4
    assert [i["rank"] for i in resp4.json()["items"]] == [1, 2, 2, 4]


def test_department_summary_avg_work_hours_half_up_boundary(client):
    """
    Test exact half-up rounding boundary case:
    Two records with 9.00 and 0.01 work hours.
    Sum = 9.01, count = 2.
    Mean = 9.01 / 2 = 4.505.
    Under strict half-up rounding (R8), .005 rounds UP to .01, so 4.505 must round to 4.51!
    Binary float division would result in 4.50499999999999989... which incorrectly rounds to 4.50.
    """
    client.post("/employees", json={
        "emp_code": "EMP0071", "name": "Bnd1", "email": "bnd1@test.com", "department": "Finance",
        "joined_on": "2026-01-01", "shift_start": "09:30", "shift_end": "18:30"
    })
    client.post("/employees", json={
        "emp_code": "EMP0072", "name": "Bnd2", "email": "bnd2@test.com", "department": "Finance",
        "joined_on": "2026-01-01", "shift_start": "09:30", "shift_end": "18:30"
    })

    # EMP0071: 9.00 hours (1767240000000 to 1767272400000)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0071", "punched_at": 1767240000000})
    client.post("/attendance/punch-out", json={"emp_code": "EMP0071", "punched_at": 1767272400000})

    # EMP0072: 0.01 hours (36 seconds = 0.01 hours: 1767240000000 to 1767240036000)
    client.post("/attendance/punch-in", json={"emp_code": "EMP0072", "punched_at": 1767240000000})
    client.post("/attendance/punch-out", json={"emp_code": "EMP0072", "punched_at": 1767240036000})

    resp = client.get("/analytics/departments/summary?month=2026-01&department=Finance")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    # 4.505 rounded half-up to 2 decimals is 4.51
    assert items[0]["avg_work_hours"] == 4.51



