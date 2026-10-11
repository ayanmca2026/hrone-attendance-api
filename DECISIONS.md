# Technical Decisions & Architecture Reference

This document answers the five core architectural questions required by the HROne engineering assignment and details the design principles implemented in the application.

---

### 1. Which indexes were created and why?
Five targeted indexes are initialized idempotently on startup:
1. `employees.emp_code` (unique, ASC): Enforces unique employee business codes at the database engine level and provides O(1) lookups.
2. `employees.(department, joined_on)` (compound, ASC): Powers department-scoped headcount filtering and enables covered index scans (`IXSCAN`) in summary and trend aggregations.
3. `attendance_logs.(emp_code, date)` (unique, compound, ASC): Guarantees the invariant that an employee can have at most one attendance record per IST calendar date, serving as the concurrency barrier.
4. `attendance_logs.(date, emp_code)` (compound, `date` DESC, `emp_code` ASC): Satisfies sorting and pagination requirements for `GET /attendance` without in-memory sort stages.
5. `attendance_logs.(emp_code, punch_in)` (compound, `emp_code` ASC, `punch_in` DESC): Allows instant retrieval of an employee's latest unclosed punch-in during `POST /attendance/punch-out`.

---

### 2. What exactly happens when two identical punch-ins arrive at the same instant?
1. Both requests are processed concurrently by FastAPI and compute the identical IST attendance date `date` from the punch-in instant.
2. Both attempt an `insert_one` into `attendance_logs`.
3. The unique compound index on `(emp_code, date)` enforces atomicity at the MongoDB engine layer.
4. Exactly one request successfully commits and returns `201 Created`.
5. The concurrent request encounters a `DuplicateKeyError` (E11000), which the API catches and cleanly maps to `409 Conflict` (`"Already punched in for this date"`). No duplicate records or corrupted states can occur.

---

### 3. What does your leaderboard return for a tie at the cutoff?
1. The leaderboard calculates standard competition ranking using MongoDB's `$setWindowFields` with the `$rank` operator (e.g. 1, 2, 2, 4).
2. Per the contract specification, `limit` applies strictly **after** ranking (`$match: {"rank": {"$lte": limit}}`).
3. If multiple employees tie at or below the cutoff rank (for example, ranks 1, 2, 2 with `limit=2`), all employees satisfying `rank <= limit` are returned. The response deliberately contains more than `limit` rows to avoid arbitrary exclusion of tied candidates.
4. Rows are deterministically ordered by `total_late_minutes` descending, then `emp_code` ascending.

---

### 4. How does your department summary count employees with no logs?
1. The aggregation pipeline originates on the `employees` collection rather than `attendance_logs`.
2. It matches employees belonging to the department whose `joined_on` date is on or before the end of the query month (`joined_on <= end_date`).
3. It performs a `$lookup` against `attendance_logs` for dates within the month. Employees with zero logs produce an empty array (`logs: []`).
4. In the subsequent `$group` stage by department, `headcount` sums `1` for every matched employee regardless of whether their `logs` array is empty. Log metrics (`present_days`, `wh_sum`, `late_count`) evaluate to `0`. Employees joining after the month are excluded upfront.

---

### 5. What would you change for 100 times the data (~10M attendance records)?
1. **Asynchronous Architecture:** Migrate from synchronous PyMongo to Motor / AsyncIO to maximize I/O throughput under high concurrency.
2. **Horizontal Sharding:** Shard the `attendance_logs` collection using a compound shard key `(emp_code, date)` to distribute storage and write operations across shards.
3. **Pre-aggregation & Materialized Rollups:** Raw log aggregations across millions of documents would be replaced with nightly or incremental rollups (e.g., MongoDB `$merge` or MongoDB Time Series collections) storing daily departmental totals. Analytics queries would read pre-computed daily buckets rather than executing cross-collection `$lookup` operations over raw logs.
4. **Read Preference & Caching:** Route read-heavy analytics to secondary replicas with caching for historical months.
