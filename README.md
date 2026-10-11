# Employee Attendance & Analytics API (HROne)

A production-grade backend service for employee attendance tracking, shift management, regularization workflows, and real-time MongoDB aggregation analytics. Built with Python 3.11+, FastAPI, Pydantic, and PyMongo.

---

## 1. Project Overview & Features

This system provides a reliable, high-performance REST API designed to handle daily enterprise attendance operations and deliver instant analytics over large-scale datasets (~100k+ attendance logs) without loading raw documents into application memory.

### Key Capabilities
- **Employee Management:** Create and query employee profiles with custom shifts, departments, and joining dates. Enforces unique business employee codes (`emp_code`) at the database engine level.
- **Attendance Operations:**
  - Race-safe punch-in with automatic IST calendar date assignment (including overnight shifts) and grace-period late calculations.
  - Atomic punch-out with half-up rounded work hours calculation, half-day evaluation, and overtime tracking.
  - Multi-criteria paginated attendance log querying backed by composite indexes.
- **Regularization & Audit Trail:**
  - Optimistic locking (`find_one_and_update`) to correct punch times or status without lost updates.
  - Complete, tamper-evident audit history capturing timestamp, editor identity, justification, and diffs of changed fields.
- **Pure MongoDB Aggregation Analytics:**
  - **Employee Monthly Summary:** Working days, present days (`0.5` for half days), leave counts, late arrival metrics, and attendance percentage.
  - **Department Summary:** Cross-collection aggregation computing headcount (including employees with zero logs), total present days, late statistics, and exact record-level average work hours over presence records.
  - **Late Leaderboard:** Standard competition ranking (`1, 2, 2, 4`) using `$setWindowFields` / `$rank` with deterministic tie-breaking and post-ranking limit filtering.
  - **Department Trend:** Gap-filled daily time series over arbitrary date ranges (up to 92 days) reporting headcount, daily present counts (weekdays & weekends), working-day attendance rates, and a 7-calendar-day moving average.
- **Admin Diagnostics & Security:** Dedicated `/admin/explain/{endpoint}` endpoint to prove query execution plans use index scans (`IXSCAN`) and eliminate collection scans (`COLLSCAN`), protected by environment toggles and optional API key authentication.
- **Readiness Probe:** `/health` endpoint validating active database ping connectivity.

---

## 2. Technology Stack & Prerequisites

- **Python:** 3.11 or newer (compatible with Python 3.11, 3.12, 3.13)
- **FastAPI:** 0.115+ (high-performance ASGI web framework)
- **Uvicorn:** 0.34+ (ASGI production web server)
- **MongoDB:** 6.0 or newer (supports `$setWindowFields`, `$dateAdd`, and compound indexing)
- **PyMongo:** 4.10+ (official synchronous MongoDB Python driver)
- **Pydantic:** 2.10+ (strict schema validation and type coercion)
- **Pytest:** 8.0+ (automated testing suite with `fastapi.testclient.TestClient`)

---

## 3. Project Directory Structure

```text
candidate_kit/
├── .gitignore               # Git ignored patterns (.venv, __pycache__, .env, etc.)
├── app/
│   ├── __init__.py
│   └── main.py              # Application entrypoint, FastAPI routes, models & aggregations
├── tests/
│   ├── conftest.py          # Pytest fixtures and isolated test DB configuration
│   ├── test_analytics.py    # Analytics tests (monthly, summary, leaderboard, trend edge cases)
│   ├── test_attendance.py   # Punch-in, punch-out, overnight shift, and listing tests
│   ├── test_employees.py    # Employee creation, duplicate prevention, and validation tests
│   ├── test_explain.py      # Admin explain endpoint & IXSCAN execution plan verification
│   ├── test_health.py       # Health check probe and database availability tests
│   ├── test_regularization.py# Manual attendance correction and audit history tests
│   └── test_seed.py         # Database seeding safety guards and idempotency tests
├── sample_data/
│   ├── attendance_logs.json # Extended JSON reference attendance logs
│   └── employees.json       # Extended JSON reference employee records
├── requirements.txt         # Pinned project dependencies
├── sample_seed.py           # Safe database seeder with non-destructive upserts and safety guards
├── openapi.yaml             # Complete OpenAPI 3.0.3 specification contract
├── DATA_MODEL.md            # Database schema documentation and extended JSON samples
├── DECISIONS.md             # Technical design choices and architectural rationale
├── REVIEW.md                # Audit report detailing defects identified and resolved
└── README.md                # Project documentation and operational guide
```

---

## 4. Windows PowerShell Setup & Installation

Follow these steps from the `candidate_kit` project root in Windows PowerShell:

### Step 1: Create and Activate Virtual Environment
```powershell
# Create a virtual environment using Python 3.11+
python -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1
```

> *Tip: If script execution is restricted in PowerShell, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` for the current terminal session.*

### Step 2: Install Dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## 5. MongoDB Configuration & Environment Variables

The application loads connection parameters from environment variables (or a local `.env` file). Real environment variables always take precedence.

| Variable | Default Value | Description |
|---|---|---|
| `MONGO_URI` | `mongodb://127.0.0.1:27017` | MongoDB connection URI string |
| `MONGO_DB` | `hrone_attendance` | Target database name for application runtime |
| `ENABLE_ADMIN_EXPLAIN` | `true` | Set to `false` in production to disable `/admin/explain/{endpoint}` |
| `ADMIN_API_KEY` | *(None)* | Optional secret key required via `X-Admin-Key` header for explain endpoint |

### Startup Index Initialization
All database indexes are automatically and idempotently initialized on application startup via the FastAPI `lifespan` handler (`init_indexes`):
- `employees.emp_code`: Unique ascending index
- `employees.(department, joined_on)`: Compound ascending index
- `attendance_logs.(emp_code, date)`: Unique compound ascending index
- `attendance_logs.(date, emp_code)`: Compound index (`date` DESC, `emp_code` ASC)
- `attendance_logs.(emp_code, punch_in)`: Compound index (`emp_code` ASC, `punch_in` DESC)

---

## 6. Safe Database Initialization & Seeding

`sample_seed.py` is configured with strict safety mechanisms to prevent accidental data loss:

1. **Default Mode (Safe Idempotent Upsert):**
   Running `python sample_seed.py` uses `replace_one(..., upsert=True)`. It **never deletes** existing user records or unrelated collections.
2. **Destructive Reset Guard (`--reset`):**
   If `--reset` or `ALLOW_DESTRUCTIVE_SEED=true` is passed, the script checks the database name. It **refuses to delete data** on production or default databases unless the database name contains a disposable marker (`test`, `sample`, `dev`, `sandbox`, `temp`, `disposable`) or `CONFIRM_RESET_DATABASE=yes` is explicitly declared.

### Safe Seeding Execution:
```powershell
# Safe idempotent upsert into the configured database:
python sample_seed.py

# Seeding into a dedicated sandbox database:
$env:MONGO_DB="hrone_sandbox"
python sample_seed.py
Remove-Item Env:\MONGO_DB
```

---

## 7. Server Startup Instructions

### Start Server on Default Port (8000)
```powershell
uvicorn app.main:app --port 8000 --reload
```

### Start Server on Port 8080
```powershell
uvicorn app.main:app --port 8080
```

### Interactive Documentation URLs
Once the server is running on `http://127.0.0.1:8000`:
- **Swagger UI (Interactive OpenAPI):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc UI:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Raw OpenAPI Specification:** [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

---

## 8. Complete API Endpoint Reference with Examples

All timestamps representing instants (`punched_at`, `punch_in`, `punch_out`, `created_at`, `history[].at`) are **epoch milliseconds** (`int64`). Calendar dates are `YYYY-MM-DD` (IST), calendar months are `YYYY-MM`, and shift times are `HH:MM` (24-hour IST).

### 8.1 System Health
#### `GET /health`
Readiness probe verifying MongoDB responsiveness via a `ping` command.
- **Response:** `200 OK`
  ```json
  {"status": "ok"}
  ```

---

### 8.2 Employee Management
#### `POST /employees`
Creates a new employee profile. Enforces unique `emp_code`.
- **Status:** `201 Created` (or `409 Conflict` if `emp_code` exists)
- **Request:**
  ```powershell
  curl -X POST http://127.0.0.1:8000/employees `
    -H "Content-Type: application/json" `
    -d '{
      "emp_code": "EMP0101",
      "name": "Aarav Sharma",
      "email": "aarav@example.com",
      "department": "Engineering",
      "shift_start": "09:30",
      "shift_end": "18:30",
      "joined_on": "2026-01-01"
    }'
  ```
- **Response (`201 Created`):**
  ```json
  {
    "emp_code": "EMP0101",
    "name": "Aarav Sharma",
    "email": "aarav@example.com",
    "department": "Engineering",
    "shift_start": "09:30",
    "shift_end": "18:30",
    "joined_on": "2026-01-01",
    "created_at": 1767240000000
  }
  ```

#### `GET /employees`
Paginated employee listing sorted by `emp_code` ascending.
- **Query Parameters:** `department` (optional), `page` (default 1), `page_size` (default 20, max 100).
- **Request:**
  ```powershell
  curl "http://127.0.0.1:8000/employees?department=Engineering&page=1&page_size=2"
  ```
- **Response (`200 OK`):**
  ```json
  {
    "items": [
      {
        "emp_code": "EMP0001",
        "name": "Asha Rao",
        "email": "asha@example.com",
        "department": "Engineering",
        "shift_start": "09:30",
        "shift_end": "18:30",
        "joined_on": "2026-01-05",
        "created_at": 1767587400000
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 2
  }
  ```

---

### 8.3 Attendance Operations
#### `POST /attendance/punch-in`
Creates a daily attendance log. Applies business rules R1 (attendance date & overnight shift adjustment) and R2 (late calculation with 10-minute grace period).
- **Status:** `201 Created` (or `409 Conflict` if record already exists for date)
- **Request:**
  ```powershell
  curl -X POST http://127.0.0.1:8000/attendance/punch-in `
    -H "Content-Type: application/json" `
    -d '{
      "emp_code": "EMP0101",
      "punched_at": 1767240000000,
      "status": "PRESENT"
    }'
  ```
- **Response (`201 Created`):**
  ```json
  {
    "emp_code": "EMP0101",
    "date": "2026-01-01",
    "status": "PRESENT",
    "punch_in": 1767240000000,
    "punch_out": null,
    "work_hours": null,
    "late_minutes": 0,
    "overtime_minutes": 0,
    "half_day": false,
    "history": []
  }
  ```

#### `POST /attendance/punch-out`
Records punch-out for the employee's latest open punch-in. Computes `work_hours` (R4), `overtime_minutes` (R3), and `half_day` (R5).
- **Status:** `200 OK` (or `409 Conflict` if already punched out; `422 Unprocessable Entity` if duration invalid)
- **Request:**
  ```powershell
  curl -X POST http://127.0.0.1:8000/attendance/punch-out `
    -H "Content-Type: application/json" `
    -d '{
      "emp_code": "EMP0101",
      "punched_at": 1767272400000
    }'
  ```
- **Response (`200 OK`):**
  ```json
  {
    "emp_code": "EMP0101",
    "date": "2026-01-01",
    "status": "PRESENT",
    "punch_in": 1767240000000,
    "punch_out": 1767272400000,
    "work_hours": 9.0,
    "late_minutes": 0,
    "overtime_minutes": 0,
    "half_day": false,
    "history": []
  }
  ```

#### `GET /attendance`
Paginated search over attendance logs sorted by `date` descending, then `emp_code` ascending.
- **Query Parameters:** `emp_code`, `date_from`, `date_to`, `status`, `page`, `page_size`.
- **Request:**
  ```powershell
  curl "http://127.0.0.1:8000/attendance?emp_code=EMP0101&date_from=2026-01-01&date_to=2026-01-31"
  ```
- **Response (`200 OK`):**
  ```json
  {
    "items": [
      {
        "emp_code": "EMP0101",
        "date": "2026-01-01",
        "status": "PRESENT",
        "punch_in": 1767240000000,
        "punch_out": 1767272400000,
        "work_hours": 9.0,
        "late_minutes": 0,
        "overtime_minutes": 0,
        "half_day": false,
        "history": []
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  }
  ```

---

### 8.4 Attendance Regularization
#### `PATCH /attendance/{emp_code}/{date}`
Adjusts punch records with optimistic locking, recomputes derived fields, and appends an immutable audit entry.
- **Request:**
  ```powershell
  curl -X PATCH http://127.0.0.1:8000/attendance/EMP0101/2026-01-01 `
    -H "Content-Type: application/json" `
    -d '{
      "status": "PRESENT",
      "punch_in": 1767240601000,
      "reason": "Corrected late arrival punch time",
      "regularized_by": "HR.Admin"
    }'
  ```
- **Response (`200 OK`):**
  ```json
  {
    "emp_code": "EMP0101",
    "date": "2026-01-01",
    "status": "PRESENT",
    "punch_in": 1767240601000,
    "punch_out": 1767272400000,
    "work_hours": 8.83,
    "late_minutes": 10,
    "overtime_minutes": 0,
    "half_day": false,
    "history": [
      {
        "at": 1767300000000,
        "by": "HR.Admin",
        "reason": "Corrected late arrival punch time",
        "changes": {
          "punch_in": {"from": 1767240000000, "to": 1767240601000},
          "late_minutes": {"from": 0, "to": 10},
          "work_hours": {"from": 9.0, "to": 8.83}
        }
      }
    ]
  }
  ```

---

### 8.5 Analytics Endpoints
#### `GET /analytics/employees/{emp_code}/monthly`
- **Request:**
  ```powershell
  curl "http://127.0.0.1:8000/analytics/employees/EMP0101/monthly?month=2026-01"
  ```
- **Response (`200 OK`):**
  ```json
  {
    "emp_code": "EMP0101",
    "month": "2026-01",
    "working_days": 22,
    "present_days": 1.0,
    "leave_days": 0,
    "late_count": 0,
    "total_late_minutes": 0,
    "total_overtime_minutes": 0,
    "attendance_pct": 4.55
  }
  ```

#### `GET /analytics/departments/summary`
- **Request:**
  ```powershell
  curl "http://127.0.0.1:8000/analytics/departments/summary?month=2026-01&department=Engineering"
  ```
- **Response (`200 OK`):**
  ```json
  {
    "month": "2026-01",
    "items": [
      {
        "department": "Engineering",
        "headcount": 1,
        "present_days": 1.0,
        "avg_work_hours": 9.0,
        "late_count": 0,
        "total_late_minutes": 0,
        "leave_count": 0,
        "on_duty_count": 0
      }
    ]
  }
  ```

#### `GET /analytics/leaderboard/late`
- **Request:**
  ```powershell
  curl "http://127.0.0.1:8000/analytics/leaderboard/late?month=2026-01&limit=5"
  ```
- **Response (`200 OK`):**
  ```json
  {
    "month": "2026-01",
    "items": [
      {
        "rank": 1,
        "emp_code": "EMP0002",
        "name": "Vikram Shah",
        "department": "Engineering",
        "total_late_minutes": 35,
        "late_count": 1
      }
    ]
  }
  ```

#### `GET /analytics/departments/{department}/trend`
- **Request:**
  ```powershell
  curl "http://127.0.0.1:8000/analytics/departments/Engineering/trend?from=2026-01-01&to=2026-01-03"
  ```
- **Response (`200 OK`):**
  ```json
  {
    "department": "Engineering",
    "items": [
      {
        "date": "2026-01-01",
        "is_working_day": true,
        "headcount": 1,
        "present_count": 1.0,
        "late_count": 0,
        "attendance_rate": 1.0,
        "moving_avg_7d": 1.0
      },
      {
        "date": "2026-01-02",
        "is_working_day": true,
        "headcount": 1,
        "present_count": 0.5,
        "late_count": 0,
        "attendance_rate": 0.5,
        "moving_avg_7d": 0.75
      },
      {
        "date": "2026-01-03",
        "is_working_day": false,
        "headcount": 1,
        "present_count": 0.5,
        "late_count": 0,
        "attendance_rate": null,
        "moving_avg_7d": 0.75
      }
    ]
  }
  ```

---

### 8.6 Admin Diagnostics & Explain
#### `GET /admin/explain/{endpoint}`
- **Path Parameter `endpoint`:** One of `attendance_list`, `employee_monthly`, `department_summary`, `late_leaderboard`, `department_trend`.
- **Query Parameters:** Same parameters required by the target endpoint.
- **Request:**
  ```powershell
  curl "http://127.0.0.1:8000/admin/explain/department_trend?department=Engineering&from=2026-01-01&to=2026-01-05"
  ```
- **Response (`200 OK`):**
  ```json
  {
    "endpoint": "department_trend",
    "collection": "employees",
    "explain": {
      "explainVersion": "1",
      "stages": [
        {
          "$cursor": {
            "queryPlanner": {
              "winningPlan": {
                "stage": "IXSCAN",
                "indexName": "department_1_joined_on_1"
              }
            }
          }
        }
      ]
    }
  }
  ```

---

## 9. Analytics Edge Cases & Business Rules

### Edge Case A — Department Average Work Hours
- **Business Rule:**
  `avg_work_hours` in `/analytics/departments/summary` is defined as the mean `work_hours` across all records whose status belongs to `PRESENCE_STATUS` (`PRESENT`, `WFH`, `ON_DUTY`) and whose stored `work_hours` value is **not null**.
- **Scope & Aggregation Level:**
  The calculation is an overall average across all qualifying records in the department (sum of work hours across all qualifying records divided by total qualifying records), **not** an average of per-employee averages.
- **Null Handling:**
  Records with `work_hours: null` (such as active punch-ins where punch-out has not yet occurred, or non-presence records like `ABSENT` and `LEAVE`) are completely excluded from both the hours sum and the record count. If a department has no records with non-null work hours, `avg_work_hours` returns `null`.
- **Short Sessions & Thresholds:**
  No arbitrary minimum-hours threshold is introduced. Legitimate short sessions (for example, a 72-second session yielding `0.02` work hours) are included. When combined with a standard 9.00-hour shift, the resulting department average is `(9.00 + 0.02) / 2 = 4.51` hours.
- **Precision:**
  The calculation utilizes Python's `Decimal` with `ROUND_HALF_UP` to prevent floating-point division inaccuracies at half-up rounding boundaries (e.g. `9.01 / 2 = 4.505` correctly rounds up to `4.51`).

### Edge Case B — Department Trend & Moving Average
- **Business Rule:**
  `/analytics/departments/{department}/trend` generates exactly one row per calendar day between `from` and `to` inclusive (using database gap filling via `$range` and `$dateAdd`).
- **Working Days vs. Non-Working Days:**
  - `is_working_day` is `true` for Monday through Friday, and `false` for Saturday and Sunday.
  - `present_count` reports all presence-status records on that calendar day (half-day counting as 0.5), including weekend records. Weekend work is explicitly tracked in `present_count`.
  - `attendance_rate` (`present_count / headcount`) is computed **only on working days where headcount > 0**. On non-working days (weekends) or when headcount is 0, `attendance_rate` is strictly `null`. A working day with no records has rate `0.0000`.
- **7-Calendar-Day Document Window & Moving Average:**
  - The moving average (`moving_avg_7d`) is evaluated using `$setWindowFields` over the document window `{"documents": [-6, 0]}` (the current day and up to 6 preceding days inside the requested range).
  - Because MongoDB's `$avg` operator natively ignores `null` values, the non-working-day `null` rates on weekends are skipped in the calculation and do not depress the moving average.
  - If a window contains no non-null rate values (e.g., query starting on a weekend), `moving_avg_7d` is `null`. Both rates and moving averages are rounded half-up to 4 decimal places.

---

## 10. Security & Production Deployment Considerations

1. **Administrative Endpoint Protection:**
   The `/admin/explain/{endpoint}` diagnostic route exposes raw query plans and execution profiles. In production:
   - Disable it entirely by setting `ENABLE_ADMIN_EXPLAIN=false` (returns `403 Forbidden`).
   - Or enforce authorization by setting `ADMIN_API_KEY=<secret>` and passing `X-Admin-Key: <secret>`.
2. **Database Hardening:**
   Never expose MongoDB without TLS encryption and dedicated user credentials with least-privilege roles.
3. **Monolithic Architecture & PyMongo:**
   The application uses synchronous PyMongo inside FastAPI. For ultra-high concurrency (10,000+ req/sec), run multiple Uvicorn worker processes behind an Nginx/ALB reverse proxy or transition to Motor (async).

---

## 11. Troubleshooting Common Issues

- **MongoDB Connection Refused:**
  Ensure MongoDB service is running (`Get-Service MongoDB` or `mongod`). Check that `MONGO_URI` matches your local or Atlas connection string.
- **PowerShell Script Execution Policy Error:**
  Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` to enable virtual environment activation in the current terminal.
- **Port 8000 in Use:**
  Run `uvicorn app.main:app --port 8080` to launch on an alternative port.
- **Timezone Drift:**
  Instants sent to the API must be valid UTC epoch milliseconds. The server translates them to IST (`UTC+05:30`) for attendance date attribution and shift calculation.

---

## 12. Automated Test Execution

The test suite provides comprehensive coverage of all API contracts, validation edge cases, race conditions, and analytics aggregation rules. Tests execute against an isolated test database (`hrone_attendance_test`) defined in `tests/conftest.py`.

```powershell
# Run the complete test suite
python -m pytest -v

# Validate bytecode compilation
python -m compileall -q app tests
```
