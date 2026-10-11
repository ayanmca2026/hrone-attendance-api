
# Employee Attendance & Analytics API (HROne)

A Python REST API for employee management, attendance tracking, shift-based calculations, attendance regularization, and MongoDB-powered analytics. The application uses FastAPI, Pydantic, PyMongo, and MongoDB.

## Table of Contents

- [Overview](#1-project-overview)
- [Features](#2-features)
- [Technology Stack](#3-technology-stack)
- [Project Structure](#4-project-structure)
- [Installation](#5-installation-on-windows)
- [MongoDB Configuration](#6-mongodb-configuration)
- [Database Initialization and Seeding](#7-database-initialization-and-seeding)
- [Run the API](#8-running-the-api)
- [API Endpoints](#9-api-endpoints)
- [Analytics and Business Rules](#10-analytics-and-business-rules)
- [Admin Diagnostics](#11-admin-diagnostics)
- [Testing](#12-testing)
- [Troubleshooting](#13-troubleshooting)
- [Security Considerations](#14-security-considerations)

---

## 1. Project Overview

The Employee Attendance & Analytics API manages employee profiles and daily attendance records. It supports punch-in and punch-out operations, shift-aware calculations, attendance corrections, audit history, and reporting endpoints.

MongoDB stores employee and attendance data. Supported analytics use database aggregation pipelines to calculate summaries and trends.

## 2. Features

### Employee Management
- Create employee profiles.
- Store employee codes, names, departments, shift times, and joining dates.
- Validate employee data.
- Enforce unique employee codes through a database index, if configured successfully.
- Retrieve employees with pagination and supported filters.

### Attendance Management
- Record employee punch-in and punch-out times.
- Associate attendance records with calendar dates.
- Apply shift-aware attendance calculations.
- Calculate late-arrival minutes, work hours, half-day status, and overtime where implemented.
- List attendance records using supported filters and pagination.
- Handle duplicate attendance operations and invalid requests.

### Regularization and Audit History
- Correct supported attendance fields through a regularization endpoint.
- Record correction details, such as editor identity, reason, timestamp, and changed values, where implemented.
- Recalculate derived attendance fields when supported by the application.
- Use an audit history for traceability. An application-level history does not, by itself, guarantee tamper-proof storage.

### Analytics
- Employee monthly attendance summaries.
- Department attendance summaries.
- Late-arrival leaderboard.
- Department attendance trends.
- Aggregation-based reporting and supported date-range calculations.

### Operational Endpoints
- Database health or readiness checks.
- Optional administrative query-plan diagnostics.
- Interactive API documentation through Swagger UI.

## 3. Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.11+ | Backend programming language |
| FastAPI | REST API framework |
| Uvicorn | ASGI server |
| Pydantic | Request and response validation |
| PyMongo | MongoDB access |
| MongoDB | Document database and aggregation |
| Pytest | Automated testing |
| Swagger UI / OpenAPI | API exploration and documentation |

Use the versions specified in `requirements.txt` as the authoritative dependency list.

## 4. Project Structure

The following is a representative structure. Keep it synchronized with the files actually present in the repository.

```text
hrone-attendance-api/
├── app/
│   ├── __init__.py
│   └── main.py
├── tests/
│   ├── conftest.py
│   ├── test_analytics.py
│   ├── test_attendance.py
│   ├── test_employees.py
│   ├── test_explain.py
│   ├── test_health.py
│   ├── test_regularization.py
│   └── test_seed.py
├── sample_data/
│   ├── attendance_logs.json
│   └── employees.json
├── .gitignore
├── requirements.txt
├── sample_seed.py
├── openapi.yaml
├── DATA_MODEL.md
├── DECISIONS.md
├── REVIEW.md
└── README.md
```

Remove any entries above that do not exist in the repository.

## 5. Installation on Windows

Open Windows PowerShell and navigate to the repository:

```powershell
cd C:\Users\Hp\hrone-attendance-api
```

### Step 1: Check Python

```powershell
python --version
```

Use a Python version compatible with the dependencies listed in `requirements.txt`.

### Step 2: Create a virtual environment

If the project does not already have a working `.venv`:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, allow scripts for the current terminal session only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

Then activate the environment again.

### Step 3: Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If `.venv` already exists and is working, reuse it rather than creating another environment unnecessarily.

## 6. MongoDB Configuration

The API requires a reachable MongoDB instance for database-backed operations.

You can use a local MongoDB installation or a properly configured MongoDB Atlas deployment.

The configuration below reflects the settings described in the current project documentation. **Verify the defaults and loading behavior in `app/main.py` before relying on them.**

| Variable | Documented default | Purpose |
|---|---|---|
| `MONGO_URI` | `mongodb://127.0.0.1:27017` | MongoDB connection URI |
| `MONGO_DB` | `hrone_attendance` | Application database name |
| `ENABLE_ADMIN_EXPLAIN` | `true` | Documented toggle for the explain endpoint |
| `ADMIN_API_KEY` | Unset | Optional admin key, depending on actual authorization logic |

Configure environment variables in PowerShell when necessary:

```powershell
$env:MONGO_URI = "mongodb://127.0.0.1:27017"
$env:MONGO_DB = "hrone_attendance"
```

These values apply to the current PowerShell session.

Do not commit real database credentials, passwords, API keys, or `.env` files to GitHub.

### MongoDB Indexes

The application documentation describes indexes intended for operations such as:

- Employee lookup by employee code.
- Employee filtering by department and joining date.
- Attendance lookup by employee and date.
- Attendance listing by date and employee code.
- Attendance lookup by employee and punch-in time.

Confirm the actual index definitions and names in the application code. Index creation can fail if existing data violates a unique constraint.

## 7. Database Initialization and Seeding

If `sample_seed.py` exists and is supported by the current implementation, it can be used to load sample data.

Run it from the project root:

```powershell
python sample_seed.py
```

Before using a destructive reset option, inspect the script and confirm the selected database is disposable.

Never run a reset against production or a database containing important records. Confirm the actual safeguards and command-line options in `sample_seed.py` before using them.

## 8. Running the API

Start the API from the project root.

If `app.main:app` is the application's verified entry point, use:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

If the virtual environment is activated and the entry point is confirmed, this equivalent command can be used:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

### API Documentation

Once the server starts successfully:

- **Swagger UI:** http://127.0.0.1:8080/docs
- **ReDoc:** http://127.0.0.1:8080/redoc
- **OpenAPI JSON:** http://127.0.0.1:8080/openapi.json
- **Health check:** http://127.0.0.1:8080/health

The ReDoc, OpenAPI, and health URLs are available only if enabled or implemented by the application.

The `/docs` address is local to your computer. The server must be running for the page to load.

## 9. API Endpoints

The following endpoints are described by the current project documentation. Confirm their paths, methods, schemas, and status codes against the running application's Swagger UI before treating this list as the definitive API contract.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Database health or readiness check |
| `POST` | `/employees` | Create an employee |
| `GET` | `/employees` | List employees with supported filters and pagination |
| `POST` | `/attendance/punch-in` | Record attendance punch-in |
| `POST` | `/attendance/punch-out` | Record attendance punch-out |
| `GET` | `/attendance` | Query attendance records |
| `PATCH` | `/attendance/{emp_code}/{date}` | Regularize an attendance record |
| `GET` | `/analytics/employees/{emp_code}/monthly` | Employee monthly summary |
| `GET` | `/analytics/departments/summary` | Department attendance summary |
| `GET` | `/analytics/leaderboard/late` | Late-arrival leaderboard |
| `GET` | `/analytics/departments/{department}/trend` | Department attendance trend |
| `GET` | `/admin/explain/{endpoint}` | Administrative query-plan diagnostics |

### 9.1 Health Check

```http
GET /health
```

Use this endpoint to check the application's reported health or database readiness. The exact response and HTTP status depend on the implementation.

Example request:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
```

### 9.2 Create an Employee

```http
POST /employees
Content-Type: application/json
```

Illustrative request body based on the documented employee fields:

```json
{
  "emp_code": "EMP0101",
  "name": "Aarav Sharma",
  "email": "aarav@example.com",
  "department": "Engineering",
  "shift_start": "09:30",
  "shift_end": "18:30",
  "joined_on": "2026-01-01"
}
```

Verify the required fields and accepted values in the employee request schema.

### 9.3 List Employees

```http
GET /employees
```

The documented endpoint supports pagination and an optional department filter.

Example:

```powershell
Invoke-RestMethod "http://127.0.0.1:8080/employees?page=1&page_size=20"
```

Check Swagger UI for the exact query parameters and defaults.

### 9.4 Punch In

```http
POST /attendance/punch-in
Content-Type: application/json
```

Illustrative request:

```json
{
  "emp_code": "EMP0101",
  "punched_at": 1767240000000,
  "status": "PRESENT"
}
```

The example assumes epoch milliseconds for `punched_at` and a `PRESENT` status because those fields are described in the existing documentation. Confirm the request schema before using this payload.

### 9.5 Punch Out

```http
POST /attendance/punch-out
Content-Type: application/json
```

Illustrative request:

```json
{
  "emp_code": "EMP0101",
  "punched_at": 1767272400000
}
```

The application may calculate work duration and derived attendance fields. The exact behavior for duplicate punch-outs, invalid durations, and missing punch-ins should be confirmed in Swagger UI and the tests.

### 9.6 List Attendance Records

```http
GET /attendance
```

Example:

```powershell
Invoke-RestMethod "http://127.0.0.1:8080/attendance?page=1&page_size=20"
```

The documented filters include employee code, date range, and attendance status. Verify exact parameter names and date inclusivity in the implementation.

### 9.7 Regularize Attendance

```http
PATCH /attendance/{emp_code}/{date}
Content-Type: application/json
```

Illustrative request body:

```json
{
  "status": "PRESENT",
  "punch_in": 1767240601000,
  "reason": "Corrected attendance punch time",
  "regularized_by": "HR.Admin"
}
```

The accepted fields, required reason, editor identity handling, and conflict behavior must match the actual regularization schema.

Where implemented, the API records correction history and recalculates derived values. An application-level audit trail should not be described as tamper-proof unless additional integrity controls exist.

### 9.8 Employee Monthly Analytics

```http
GET /analytics/employees/{emp_code}/monthly
```

Example:

```powershell
Invoke-RestMethod "http://127.0.0.1:8080/analytics/employees/EMP0101/monthly?month=2026-01"
```

Verify the accepted month format and response fields in the API documentation.

### 9.9 Department Summary

```http
GET /analytics/departments/summary
```

Example:

```powershell
Invoke-RestMethod "http://127.0.0.1:8080/analytics/departments/summary?month=2026-01"
```

Check the actual supported filters and definitions for headcount, present days, leave counts, late statistics, and average work hours.

### 9.10 Late-Arrival Leaderboard

```http
GET /analytics/leaderboard/late
```

Example:

```powershell
Invoke-RestMethod "http://127.0.0.1:8080/analytics/leaderboard/late?month=2026-01&limit=5"
```

Verify the ranking calculation, tie behavior, and accepted limit before relying on them.

### 9.11 Department Trend

```http
GET /analytics/departments/{department}/trend
```

Example:

```powershell
Invoke-RestMethod "http://127.0.0.1:8080/analytics/departments/Engineering/trend?from=2026-01-01&to=2026-01-03"
```

Confirm the supported date range, maximum number of days, treatment of weekends, and response fields in the implementation.

### 9.12 Admin Explain

```http
GET /admin/explain/{endpoint}
```

This diagnostic endpoint is intended to expose MongoDB query-plan information for supported operations, if enabled.

Example:

```powershell
Invoke-RestMethod "http://127.0.0.1:8080/admin/explain/department_trend?department=Engineering&from=2026-01-01&to=2026-01-05"
```

The actual accepted endpoint identifiers, parameters, authentication requirements, and response format must be verified against the route implementation. Do not assume the endpoint is protected simply because an API-key variable exists.

## 10. Analytics and Business Rules

Documented analytics include employee monthly summaries, department summaries, late-arrival rankings, and department trends.

The following rules should be retained in this README only after they have been verified against the implementation and regression tests.

### Department Average Work Hours

The existing documentation describes an average calculated across qualifying attendance records with non-null work-hour values, rather than an average of employee-level averages.

Verify:
- Which attendance statuses qualify.
- How incomplete punch records are handled.
- Whether short work sessions are included.
- The precision and rounding method.
- The behavior when no qualifying records exist.

### Department Trend

The existing documentation describes daily trend rows and a seven-calendar-day moving average.

Verify:
- Whether every calendar date in the requested range is included.
- How Saturdays and Sundays are treated.
- Whether weekends contribute to present counts.
- How attendance rates behave when headcount is zero.
- How null values are handled by the moving average.
- The supported maximum date range.

Avoid documenting a particular MongoDB aggregation operator or ranking implementation unless the source code confirms it.

## 11. Admin Diagnostics

If the admin explain endpoint is enabled, it can help inspect query execution plans.

Before exposing it outside local development:

1. Verify whether the endpoint is disabled by default.
2. Verify whether authentication is enforced.
3. Restrict access to authorized administrators.
4. Avoid exposing sensitive query details unnecessarily.
5. Disable the endpoint in production if it is not needed.

Do not claim every query uses an index or avoids collection scans without evidence from actual execution plans.

## 12. Testing

Run the existing test suite from the repository root.

If `.venv` exists and contains the project dependencies:

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

Check Python compilation:

```powershell
.\.venv\Scripts\python.exe -m compileall -q app tests
```

Check whitespace errors in Git changes:

```powershell
git diff --check
```

The tests may require MongoDB or specific environment variables. Review `tests/conftest.py` and the test configuration before running them.

Report the actual test results. Do not claim that tests pass or use an isolated database unless verified.

## 13. Troubleshooting

### MongoDB connection failure

- Verify that the MongoDB service is running.
- Check `MONGO_URI` and `MONGO_DB`.
- Confirm network access and credentials for MongoDB Atlas.
- Inspect the application logs for the actual connection error.

### Swagger UI does not open

- Confirm that Uvicorn started successfully.
- Confirm the server is using port `8080`.
- Open http://127.0.0.1:8080/docs.
- Check whether another process is occupying the port.
- Verify the application import path.

### Environment or dependency errors

- Activate the intended virtual environment.
- Install dependencies from `requirements.txt`.
- Confirm the Python version is compatible with the project.
- Inspect the traceback rather than suppressing the error.

### Attendance calculation discrepancies

- Verify whether timestamps are expected in epoch milliseconds or another format.
- Check the time-zone conversion and attendance-date rules.
- Review shift boundaries and rounding behavior in the implementation.
- Use the relevant regression tests to confirm expected results.

## 14. Security Considerations

- Never commit `.env` files, passwords, API keys, or database credentials.
- Use dedicated MongoDB credentials with least-privilege access.
- Use TLS for database connections when required by the deployment.
- Restrict administrative diagnostic endpoints.
- Validate incoming request data.
- Keep dependencies updated and review security advisories.
- Protect audit-history data using appropriate database permissions and operational controls.
- Configure production logging without exposing secrets or sensitive employee information.

The application should be assessed and tested in its deployment environment before making production-readiness claims.

---

## License

Add a license section only after confirming that the repository contains a valid license or the project owner has selected one.

## Project Repository

[HROne Attendance API on GitHub](https://github.com/ayanmca2026/hrone-attendance-api)

