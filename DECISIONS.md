# Technical Decisions

This document outlines the main technical and architectural decisions made while completing the HROne API assignment.

## FastAPI & PyMongo
FastAPI was selected for its high performance, excellent integration with Pydantic for request/response validation, and its automatic OpenAPI documentation generation. PyMongo (sync) was selected because the application logic heavily relies on sequential, atomic updates and the assignment constraint favors a monolithic `app/main.py`.

## MongoDB Analytics over Python processing
All analytics endpoints (Monthly, Summary, Leaderboard, Trend) use MongoDB aggregation pipelines (`$match`, `$group`, `$lookup`, `$setWindowFields`) instead of retrieving documents into Python for calculation. This avoids loading ~100k documents into application memory, vastly reducing RAM usage and latency.

## Attendance Date & Timezones
MongoDB stores all times as UTC `datetime` objects. To handle India Standard Time (IST), the timezone `UTC+05:30` is explicitly applied when computing the "attendance date" from a punch_in timestamp. 

## Overnight Shifts
Overnight shifts are dynamically detected (`shift_end <= shift_start`). For calculations involving overnight shifts, the calendar date of the shift_end is bumped to the next calendar day (`timedelta(days=1)`) ensuring proper calculation of `overtime_minutes` and accurate `late_minutes`.

## Atomicity and Concurrent Updates
Race conditions for punch-ins and regularization edits are avoided by:
1. Creating unique indexes on `emp_code` for employees and `(emp_code, date)` for attendance logs.
2. Using `find_one_and_update` for `punch_out` and regularization, which ensures atomic updates.

## Array Generation vs $densify
For the Department Trend gap-filling requirement, an approach generating an array of offsets via `$range` and `$dateAdd`, followed by an `$unwind`, was used instead of `$densify`. This ensures backward compatibility with MongoDB versions older than 5.1 while still doing all gap-filling and calculations purely on the database side without looping in Python.

## Handling of Derived Fields
Fields such as `late_minutes`, `work_hours`, `half_day`, and `overtime_minutes` are correctly computed by the API upon `punch_in`, `punch_out`, or manual edit, and then persisted. Analytics run directly against these pre-computed fields.
