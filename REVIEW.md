# HR One Assignment - Review & Defects Log

## Part A: Defects Identified & Fixed

During the comprehensive code audit, verification, and regression testing, the following critical defects and edge cases were identified and resolved:

1. **Precision Loss in `compute_work_hours`**:
   - *Defect*: The work hours calculation used standard float division (`secs / 3600`) before converting to `Decimal` for rounding. Floating-point imprecision caused boundaries (e.g., `.005`) to round incorrectly, violating the strict 'half-up' rounding requirement (R4).
   - *Fix*: Transformed the operation to use `Decimal` throughout: `Decimal(str(secs)) / Decimal('3600')` before calling `quantize`.

2. **Concurrency Issue in `regularize_attendance`**:
   - *Defect*: The atomic update (`find_one_and_update`) verified history integrity using `"history": record.get("history", [])`. For older legacy records missing the `history` field entirely, this strict equality match against an empty array would fail, causing a 409 error.
   - *Fix*: Improved the filter to handle missing fields correctly: if history is missing, it explicitly matches against `{"$exists": False}`.

3. **Falsy Timestamp Ignored in `regularize_attendance`**:
   - *Defect*: The `punch_in` and `punch_out` values were checked using truthy evaluation (`if body.punch_in:`). A valid UNIX timestamp of `0` would be incorrectly ignored and fallback to the database record's original time.
   - *Fix*: Changed to explicit `is not None` checks.

4. **Float Precision Loss in `employee_monthly` Aggregation**:
   - *Defect*: Similar to work hours, the `attendance_pct` was computed using float division `(agg['present_days'] / working_days) * 100` before `Decimal` rounding.
   - *Fix*: Converted the components to `Decimal` prior to the division to ensure exact half-up calculation.

5. **Performance Issue (`COLLSCAN`) in `department_summary`**:
   - *Defect*: The pipeline grouped by department first, collected an array of `emp_codes`, and then used a `$lookup` on `attendance_logs` containing an `$expr` with an `$in` operator. MongoDB cannot effectively utilize indexes for this operation across collections, resulting in a full collection scan (COLLSCAN) on the 100,000-record dataset.
   - *Fix*: Restructured the pipeline to `$lookup` logs per employee utilizing the standard `localField` and `foreignField` (which guarantees IXSCAN usage), computed the metrics using array operators (`$map`, `$filter`, `$reduce`), and then grouped the results by department.

6. **Severe Performance Bottleneck (`COLLSCAN` in loop) in `department_trend`**:
   - *Defect*: The pipeline generated an array of days via `$range` and unwound them, subsequently performing a nested `$lookup` on `attendance_logs` for *each day* using an `$expr` check. This caused up to 92 collection scans per execution.
   - *Fix*: Optimized the query by performing a single `$lookup` to fetch all logs for the department upfront, concatenating them in memory, and generating the days. Filtering the logs per day is now executed fully within the aggregation context using `$filter`, reducing DB index lookups to a single pass and strictly adhering to IXSCAN.

7. **Rounding Rule Violation in `department_trend`**:
   - *Defect*: The moving average and attendance rates were rounded using MongoDB's built-in `$round` operator, which uses 'half-to-even' (banker's rounding) natively. The assignment explicitly required 'half-up' rounding for rates (R8).
   - *Fix*: Implemented custom half-up mathematical rounding (`$floor` of `$add` with 0.5 multiplied by factor) natively in the aggregation pipeline.

8. **Contract Compliance for Leaderboard Tie Handling at Rank Cutoff**:
   - *Defect*: An earlier draft placed a strict `{"$limit": limit}` stage at the end of the leaderboard pipeline to artificially truncate ties to `limit` rows. However, the contract (`openapi.yaml`) explicitly specifies: *"`limit` applies after ranking: return every employee whose `rank` <= `limit`. The response can therefore contain more than `limit` rows when employees tie at a rank <= `limit`"*. Truncating with `$limit` broke this requirement.
   - *Fix*: Removed the `{"$limit": limit}` restriction, relying on `{"$match": {"rank": {"$lte": limit}}}` and deterministic tie-breaking order `{"$sort": {"total_late_minutes": -1, "_id": 1}}`. When candidates tie at or below the cutoff rank, all are returned.

9. **Server Crash (HTTP 500) on Invalid Month strings**:
   - *Defect*: `parse_month` threw a generic `ValueError` when `date()` was initialized with an invalid month (e.g. `2026-15`), causing the application to throw an internal server error instead of a 422 Unprocessable Entity.
   - *Fix*: Wrapped the conversion logic in a `try-except` block and gracefully returned a `HTTPException(422)`.

10. **Query String Validation bypass in `list_attendance`**:
    - *Defect*: Query variables `date_from` and `date_to` were typed strictly as `str` strings without validation, allowing malformed strings to flow directly into the MongoDB query.
    - *Fix*: Enforced `date_type.fromisoformat()` validation to reject malformed payloads with 422.

11. **Float Division Inaccuracy in `department_summary` `avg_work_hours`**:
    - *Defect*: `avg_work_hours` performed binary float division `Decimal(wh_sum / wh_count)` before calling `quantize`. For boundary values like `9.01 / 2 = 4.505`, binary floating-point representation resulted in `4.50499999999999989...`, causing `ROUND_HALF_UP` to round down to `4.50` instead of `4.51`.
    - *Fix*: Replaced with deliberate decimal division `(Decimal(str(round(wh_sum, 4))) / Decimal(wh_count)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`. Correctly preserves legitimate short sessions (e.g. 0.02 hours) without arbitrary thresholds.

12. **Unprotected Administrative Diagnostics & Missing Parameter Validation in Explain Endpoint**:
    - *Defect*: `/admin/explain/{endpoint}` lacked production security controls, allowing unauthorized clients to inspect query execution statistics. Furthermore, parameters such as `limit`, `page`, `page_size`, `date_from`, `date_to`, and `status` were not validated against schemas.
    - *Fix*: Added `ENABLE_ADMIN_EXPLAIN` environment toggle to disable explain in production (returns 403), support for `ADMIN_API_KEY` header verification (`X-Admin-Key`), and strict validation of date ranges, page limits, and status codes.

13. **Destructive Data Loss Risk in `sample_seed.py`**:
    - *Defect*: `sample_seed.py` ran blanket `delete_many({})` against `employees` and `attendance_logs`, posing severe risk of permanent data loss on real or development databases.
    - *Fix*: Re-architected seeding to default to safe, idempotent upserts (`replace_one(..., upsert=True)`). Destructive mode (`--reset`) is opt-in and incorporates a safety guard preventing execution on non-disposable databases unless `CONFIRM_RESET_DATABASE=yes` is explicitly declared.

14. **Path Parameter Date Validation in Regularization**:
    - *Defect*: The path parameter `date` in `PATCH /attendance/{emp_code}/{date}` was not verified as an ISO calendar date before database lookup.
    - *Fix*: Added `date_type.fromisoformat(date)` validation to ensure malformed date paths immediately return 422 Unprocessable Entity.

---

## Part B: Implementation Architecture Summary

- **`punch_out`**: 
  Identifies the latest open `punch_in` and safely commits the record using atomic `find_one_and_update`, applying R3, R4, and R5 rules for work hours, overtime, and half-day status calculations. Concurrency is guaranteed by matching strictly against `punch_out: None`.

- **`regularize_attendance`**:
  Optimistic locking on `history` integrity ensures concurrent updates cannot overwrite audit trails. Recalculates derived fields and supports partial updates cleanly.

- **`explain` / Analytics**: 
  All queries execute purely within MongoDB via index-supported aggregations (`IXSCAN`), verifiable via the `/admin/explain/` endpoint.
