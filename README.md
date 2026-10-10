# Employee Attendance & Analytics API

## Project Overview
This project implements a production-quality backend API for an employee attendance and analytics system. It is built for HROne using Python, FastAPI, and MongoDB. The system enforces business rules around punch-in/out times, overtimes, shift overlaps, and late arrivals. It also includes comprehensive analytics through pure MongoDB aggregation pipelines.

## Features
- **Employee Management:** Create and list employees with department and shift tracking.
- **Attendance Tracking:** Punch-in and punch-out operations with automatic calculations of late minutes, work hours, overtime, and half-day status based on business rules.
- **Regularization:** Manual override capabilities for HR to correct records, leaving a permanent audit trail of changed fields.
- **Analytics Dashboard:**
  - Employee monthly attendance summary.
  - Department headcount and summary.
  - Department historical trends (attendance rate and 7-day moving averages).
  - Late-comers leaderboard.
- **Admin Tools:** Direct MongoDB query EXPLAIN endpoint for performance monitoring.

## Technology Stack
- **Python 3.11+**
- **FastAPI** (for web framework & API routing)
- **Pydantic** (for data validation)
- **MongoDB 6.0+** & **PyMongo** (for persistence and aggregation)
- **Pytest** (for automated testing)

## Folder Structure
```text
hrone-attendance-api/
├── app/
│   ├── __init__.py
│   └── main.py          # Main FastAPI application
├── tests/
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_employees.py
│   ├── test_attendance.py
│   ├── test_regularization.py
│   ├── test_analytics.py
│   └── test_explain.py
├── sample_data/         # JSON data fixtures for testing/seeding
├── requirements.txt     # Python dependencies
├── sample_seed.py       # Script to load data into MongoDB
├── openapi.yaml         # Complete API OpenAPI/Swagger specification
├── DATA_MODEL.md        # Database collections reference
├── DECISIONS.md         # Technical architecture decisions
├── REVIEW.md            # Starter code review and fix log
└── README.md            # This documentation file
```

## Prerequisites
- Python 3.11 or newer
- MongoDB 6.0 or newer running locally or accessible via URI

## Setup & Execution (Windows PowerShell)

1. **Activate Virtual Environment:**
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. **Install Dependencies:**
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

3. **Start MongoDB locally (if not already running):**
Make sure your MongoDB server is active on `localhost:27017`

4. **Seed the database:**
```powershell
python sample_seed.py
```

5. **Start the FastAPI Server:**
```powershell
uvicorn app.main:app --reload
```

## Swagger Documentation
After starting the server, browse to:
http://127.0.0.1:8000/docs
This UI provides interactive documentation for all endpoints, matching the `openapi.yaml`.

## Running Automated Tests
Run the pytest suite to verify all business rules:
```powershell
python -m pytest tests/
```
The test suite spans endpoints, data validation, overlapping shift logic, and aggregation calculations.

## Environment Variables
The application relies on:
- `MONGO_URI`: Connection string (default: `mongodb://127.0.0.1:27017`)
- `MONGO_DB`: Target database name (default: `hrone_attendance`)
*(Do not commit actual secrets to the repository!)*

## Performance & Indexing
The MongoDB schema makes heavy use of specific indexing such as unique `(emp_code, date)` and grouped sorts for fast pagination. All major analytics bypass python memory processing, running entirely within MongoDB via the Aggregation Framework (`$match`, `$lookup`, `$densify` equivalent, `$setWindowFields`). 

Use the `/admin/explain/` endpoints to verify query execution plans and ensure `IXSCAN` operations instead of `COLLSCAN`.

## GitHub Submission Instructions
When preparing the project for submission:
```powershell
git init
git add .
git commit -m "Initial complete HROne implementation"
git remote add origin https://github.com/your-username/your-repo-name.git
git push -u origin main
```
