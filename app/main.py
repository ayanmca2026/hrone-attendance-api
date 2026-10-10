import os
import re
from datetime import datetime, timedelta, timezone, date as date_type
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Path, Body
from pydantic import BaseModel, Field, StrictInt, field_validator, model_validator
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
load_dotenv()

IST = timezone(timedelta(hours=5, minutes=30))

client = MongoClient(
    os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017"),
    tz_aware=True,
    serverSelectionTimeoutMS=5000,
)
db = client[os.getenv("MONGO_DB", "hrone_attendance")]

app = FastAPI(title="Employee Attendance & Analytics API", version="2.0.0")


@app.on_event("startup")
def startup_event():
    db.employees.create_index("emp_code", unique=True)
    db.employees.create_index([("department", ASCENDING), ("joined_on", ASCENDING)])
    db.attendance_logs.create_index([("emp_code", ASCENDING), ("date", ASCENDING)], unique=True)
    db.attendance_logs.create_index([("date", DESCENDING), ("emp_code", ASCENDING)])
    db.attendance_logs.create_index([("emp_code", ASCENDING), ("punch_in", DESCENDING)])


# --------------------------------------------------------------------------- #
# Constants & Helpers
# --------------------------------------------------------------------------- #
ALL_STATUS = {"PRESENT", "ABSENT", "LEAVE", "WFH", "ON_DUTY"}
PRESENCE_STATUS = {"PRESENT", "WFH", "ON_DUTY"}
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MS_MIN = 100_000_000_000
MS_MAX = 4_102_444_800_000


def truncate_dt(dt: datetime) -> datetime:
    return dt.replace(microsecond=0)


def ms_to_dt(ms: Optional[int]) -> Optional[datetime]:
    if ms is None:
        return None
    return truncate_dt(datetime.fromtimestamp(ms / 1000, tz=timezone.utc))


def dt_to_ms(dt: Optional[datetime]) -> Optional[int]:
    if dt is None:
        return None
    return int(dt.timestamp() * 1000)


def now_truncated() -> datetime:
    return truncate_dt(datetime.now(timezone.utc))


def compute_attendance_date(punch_in: datetime, shift_start: str, shift_end: str) -> str:
    """R1: IST calendar date of punch_in, adjusted for overnight shifts."""
    ist_time = punch_in.astimezone(IST)
    att_date = ist_time.date()
    
    if shift_end <= shift_start:
        eh, em = map(int, shift_end.split(":"))
        if ist_time.time() < datetime(2000, 1, 1, eh, em).time():
            att_date -= timedelta(days=1)
            
    return att_date.isoformat()


def compute_late_minutes(punch_in: datetime, shift_start: str, att_date: str) -> int:
    """R2: Grace 10 mins. Late if strictly > 600s after shift_start."""
    if not punch_in:
        return 0
    sh, sm = map(int, shift_start.split(":"))
    d = date_type.fromisoformat(att_date)
    start_dt = datetime(d.year, d.month, d.day, sh, sm, tzinfo=IST)
    diff = (punch_in - start_dt).total_seconds()
    if diff > 600:
        return int(diff // 60)
    return 0


def compute_overtime(punch_out: datetime, shift_end: str, shift_start: str, att_date: str) -> int:
    """R3: Overtime if >= 30 mins after shift_end."""
    if not punch_out:
        return 0
    eh, em = map(int, shift_end.split(":"))
    d = date_type.fromisoformat(att_date)
    if shift_end <= shift_start:
        d += timedelta(days=1)
    end_dt = datetime(d.year, d.month, d.day, eh, em, tzinfo=IST)
    diff = (punch_out - end_dt).total_seconds()
    ot_mins = int(diff // 60)
    return ot_mins if ot_mins >= 30 else 0


def compute_work_hours(punch_in: datetime, punch_out: datetime) -> Optional[float]:
    """R4: Work hours rounded to 2 decimals half-up."""
    if not punch_in or not punch_out:
        return None
    secs = (punch_out - punch_in).total_seconds()
    return float(Decimal(secs / 3600).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def compute_half_day(work_hours: Optional[float]) -> bool:
    """R5: true if rounded work_hours < 4.50"""
    if work_hours is None:
        return False
    return work_hours < 4.50


def parse_month(month: str):
    y, m = map(int, month.split("-"))
    start_date = date_type(y, m, 1)
    if m == 12:
        next_month = date_type(y + 1, 1, 1)
    else:
        next_month = date_type(y, m + 1, 1)
    end_date = next_month - timedelta(days=1)
    return start_date, end_date


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class EmployeeCreate(BaseModel):
    emp_code: str = Field(..., pattern=r"^EMP\d{4,6}$")
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    department: str = Field(..., min_length=1, max_length=50)
    shift_start: str = Field("09:30", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    shift_end: str = Field("18:30", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    joined_on: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")

    @model_validator(mode="after")
    def validate_shifts(self):
        if self.shift_start == self.shift_end:
            raise ValueError("shift_start and shift_end cannot be identical")
        # Validate date
        try:
            date_type.fromisoformat(self.joined_on)
        except ValueError:
            raise ValueError("joined_on must be a valid date")
        return self


class PunchInRequest(BaseModel):
    emp_code: str
    punched_at: Optional[StrictInt] = Field(None, ge=MS_MIN, le=MS_MAX)
    status: str = "PRESENT"

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v not in PRESENCE_STATUS:
            raise ValueError(f"status must be one of {PRESENCE_STATUS}")
        return v


class PunchOutRequest(BaseModel):
    emp_code: str
    punched_at: Optional[StrictInt] = Field(None, ge=MS_MIN, le=MS_MAX)


class RegularizeRequest(BaseModel):
    status: Optional[str] = None
    punch_in: Optional[StrictInt] = Field(None, ge=MS_MIN, le=MS_MAX)
    punch_out: Optional[StrictInt] = Field(None, ge=MS_MIN, le=MS_MAX)
    reason: str = Field(..., min_length=5, max_length=200)
    regularized_by: str = Field(..., min_length=1, max_length=50)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in ALL_STATUS:
            raise ValueError(f"status must be one of {ALL_STATUS}")
        return v


# --------------------------------------------------------------------------- #
# Response Formatting
# --------------------------------------------------------------------------- #
def format_employee(doc: dict) -> dict:
    return {
        "emp_code": doc["emp_code"],
        "name": doc["name"],
        "email": doc["email"],
        "department": doc["department"],
        "shift_start": doc["shift_start"],
        "shift_end": doc["shift_end"],
        "joined_on": doc["joined_on"],
        "created_at": dt_to_ms(doc.get("created_at")),
    }


def format_attendance(doc: dict) -> dict:
    history = []
    for h in doc.get("history", []):
        entry = {
            "at": dt_to_ms(h["at"]),
            "by": h["by"],
            "reason": h["reason"],
            "changes": {},
        }
        for k, v in h["changes"].items():
            if k in ("punch_in", "punch_out"):
                entry["changes"][k] = {
                    "from": dt_to_ms(v.get("from")) if v.get("from") else None,
                    "to": dt_to_ms(v.get("to")) if v.get("to") else None,
                }
            else:
                entry["changes"][k] = v
        history.append(entry)

    return {
        "emp_code": doc["emp_code"],
        "date": doc["date"],
        "status": doc["status"],
        "punch_in": dt_to_ms(doc.get("punch_in")),
        "punch_out": dt_to_ms(doc.get("punch_out")),
        "work_hours": doc.get("work_hours"),
        "late_minutes": doc.get("late_minutes", 0),
        "overtime_minutes": doc.get("overtime_minutes", 0),
        "half_day": doc.get("half_day", False),
        "history": history,
    }


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@app.get("/health")
def health():
    try:
        db.command("ping")
    except Exception:
        raise HTTPException(503, detail="MongoDB unavailable")
    return {"status": "ok"}


@app.post("/employees", status_code=201)
def create_employee(body: EmployeeCreate):
    doc = body.model_dump()
    doc["created_at"] = now_truncated()
    try:
        db.employees.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, detail="emp_code already exists")
    return format_employee(doc)


@app.get("/employees")
def list_employees(
    department: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    q = {}
    if department:
        q["department"] = department
    
    total = db.employees.count_documents(q)
    skip = (page - 1) * page_size
    items = list(db.employees.find(q).sort("emp_code", ASCENDING).skip(skip).limit(page_size))
    
    return {
        "items": [format_employee(d) for d in items],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@app.post("/attendance/punch-in", status_code=201)
def punch_in(body: PunchInRequest):
    emp = db.employees.find_one({"emp_code": body.emp_code})
    if not emp:
        raise HTTPException(404, detail="Employee not found")

    ts = ms_to_dt(body.punched_at) if body.punched_at else now_truncated()
    att_date = compute_attendance_date(ts, emp["shift_start"], emp["shift_end"])
    late_mins = compute_late_minutes(ts, emp["shift_start"], att_date)

    doc = {
        "emp_code": body.emp_code,
        "date": att_date,
        "status": body.status,
        "punch_in": ts,
        "punch_out": None,
        "work_hours": None,
        "late_minutes": late_mins,
        "overtime_minutes": 0,
        "half_day": False,
        "history": [],
    }
    try:
        db.attendance_logs.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, detail="Already punched in for this date")
    
    return format_attendance(doc)


@app.post("/attendance/punch-out")
def punch_out(body: PunchOutRequest):
    emp = db.employees.find_one({"emp_code": body.emp_code})
    if not emp:
        raise HTTPException(404, detail="Employee not found")

    ts = ms_to_dt(body.punched_at) if body.punched_at else now_truncated()

    record = db.attendance_logs.find_one(
        {"emp_code": body.emp_code, "punch_in": {"$lte": ts}, "status": {"$in": list(PRESENCE_STATUS)}},
        sort=[("punch_in", DESCENDING)]
    )
    if not record:
        raise HTTPException(404, detail="No valid punch-in found")

    if record.get("punch_out"):
        raise HTTPException(409, detail="Already punched out")

    if ts <= record["punch_in"] or (ts - record["punch_in"]).total_seconds() > 86400:
        raise HTTPException(422, detail="Invalid punched_at duration")

    work_hours = compute_work_hours(record["punch_in"], ts)
    overtime_mins = compute_overtime(ts, emp["shift_end"], emp["shift_start"], record["date"])
    half_day = compute_half_day(work_hours)

    res = db.attendance_logs.find_one_and_update(
        {"_id": record["_id"], "punch_out": None},
        {"$set": {
            "punch_out": ts,
            "work_hours": work_hours,
            "overtime_minutes": overtime_mins,
            "half_day": half_day
        }},
        return_document=True
    )
    if not res:
        raise HTTPException(409, detail="Conflict during punch out")

    return format_attendance(res)


@app.get("/attendance")
def list_attendance(
    emp_code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    q = {}
    if emp_code:
        q["emp_code"] = emp_code
    
    if date_from or date_to:
        q["date"] = {}
        if date_from:
            q["date"]["$gte"] = date_from
        if date_to:
            q["date"]["$lte"] = date_to
        if date_from and date_to and date_from > date_to:
            raise HTTPException(422, detail="date_from > date_to")

    if status:
        if status not in ALL_STATUS:
            raise HTTPException(422, detail="Invalid status")
        q["status"] = status

    total = db.attendance_logs.count_documents(q)
    skip = (page - 1) * page_size
    items = list(db.attendance_logs.find(q).sort([("date", DESCENDING), ("emp_code", ASCENDING)]).skip(skip).limit(page_size))

    return {
        "items": [format_attendance(d) for d in items],
        "total": total,
        "page": page,
        "page_size": page_size
    }


@app.patch("/attendance/{emp_code}/{date}")
def regularize_attendance(
    emp_code: str,
    date: str,
    body: RegularizeRequest
):
    emp = db.employees.find_one({"emp_code": emp_code})
    if not emp:
        raise HTTPException(404, detail="Employee not found")

    record = db.attendance_logs.find_one({"emp_code": emp_code, "date": date})
    if not record:
        raise HTTPException(404, detail="Attendance record not found")

    new_status = body.status if body.status is not None else record["status"]
    new_in = ms_to_dt(body.punch_in) if body.punch_in is not None else record.get("punch_in")
    new_out = ms_to_dt(body.punch_out) if body.punch_out is not None else record.get("punch_out")

    # Validation
    if new_status in {"ABSENT", "LEAVE"}:
        if body.punch_in is not None or body.punch_out is not None:
            raise HTTPException(422, detail="punch_in and punch_out not allowed with ABSENT/LEAVE")
        new_in = None
        new_out = None
    else:
        if not new_in:
            raise HTTPException(422, detail="punch_in is required for presence status")
        if compute_attendance_date(new_in, emp["shift_start"], emp["shift_end"]) != date:
            raise HTTPException(422, detail="punch_in must stay on the same attendance date")
        if new_out:
            if new_out <= new_in or (new_out - new_in).total_seconds() > 86400:
                raise HTTPException(422, detail="Invalid punch_out")

    # Recalculate
    if new_status in {"ABSENT", "LEAVE"}:
        new_late, new_wh, new_ot, new_half = 0, None, 0, False
    else:
        new_late = compute_late_minutes(new_in, emp["shift_start"], date)
        if new_out:
            new_wh = compute_work_hours(new_in, new_out)
            new_ot = compute_overtime(new_out, emp["shift_end"], emp["shift_start"], date)
            new_half = compute_half_day(new_wh)
        else:
            new_wh, new_ot, new_half = None, 0, False

    # Compute changes
    changes = {}
    current = {
        "status": record["status"],
        "punch_in": record.get("punch_in"),
        "punch_out": record.get("punch_out"),
        "work_hours": record.get("work_hours"),
        "late_minutes": record.get("late_minutes", 0),
        "overtime_minutes": record.get("overtime_minutes", 0),
        "half_day": record.get("half_day", False)
    }
    updates = {
        "status": new_status,
        "punch_in": new_in,
        "punch_out": new_out,
        "work_hours": new_wh,
        "late_minutes": new_late,
        "overtime_minutes": new_ot,
        "half_day": new_half
    }

    for k, v in updates.items():
        if current[k] != v:
            changes[k] = {"from": current[k], "to": v}

    if not changes:
        raise HTTPException(422, detail="No changes detected")

    history_entry = {
        "at": now_truncated(),
        "by": body.regularized_by,
        "reason": body.reason,
        "changes": changes
    }

    res = db.attendance_logs.find_one_and_update(
        {"_id": record["_id"], "history": record.get("history", [])},
        {
            "$set": updates,
            "$push": {"history": history_entry}
        },
        return_document=True
    )
    if not res:
        raise HTTPException(409, detail="Concurrent modification conflict")

    return format_attendance(res)


@app.get("/analytics/employees/{emp_code}/monthly")
def employee_monthly(emp_code: str, month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$")):
    emp = db.employees.find_one({"emp_code": emp_code})
    if not emp:
        raise HTTPException(404, detail="Employee not found")

    start_date, end_date = parse_month(month)
    joined_date = date_type.fromisoformat(emp["joined_on"])
    eff_start = max(start_date, joined_date)
    
    working_days = 0
    if eff_start <= end_date:
        curr = eff_start
        while curr <= end_date:
            if curr.weekday() < 5:
                working_days += 1
            curr += timedelta(days=1)

    pipeline = [
        {"$match": {
            "emp_code": emp_code,
            "date": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()}
        }},
        {"$addFields": {
            "dow": {"$dayOfWeek": {"$dateFromString": {"dateString": "$date"}}}
        }},
        {"$group": {
            "_id": None,
            "present_days": {
                "$sum": {
                    "$cond": [
                        {"$and": [
                            {"$in": ["$status", list(PRESENCE_STATUS)]},
                            {"$in": ["$dow", [2, 3, 4, 5, 6]]}
                        ]},
                        {"$cond": ["$half_day", 0.5, 1]},
                        0
                    ]
                }
            },
            "leave_days": {
                "$sum": {"$cond": [{"$eq": ["$status", "LEAVE"]}, 1, 0]}
            },
            "late_count": {
                "$sum": {"$cond": [{"$gt": ["$late_minutes", 0]}, 1, 0]}
            },
            "total_late_minutes": {"$sum": {"$ifNull": ["$late_minutes", 0]}},
            "total_overtime_minutes": {"$sum": {"$ifNull": ["$overtime_minutes", 0]}}
        }}
    ]

    res = list(db.attendance_logs.aggregate(pipeline))
    agg = res[0] if res else {
        "present_days": 0.0, "leave_days": 0, "late_count": 0,
        "total_late_minutes": 0, "total_overtime_minutes": 0
    }
    
    pct = None
    if working_days > 0:
        pct = float(Decimal((agg["present_days"] / working_days) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    return {
        "emp_code": emp_code,
        "month": month,
        "working_days": working_days,
        "present_days": agg["present_days"],
        "leave_days": agg["leave_days"],
        "late_count": agg["late_count"],
        "total_late_minutes": agg["total_late_minutes"],
        "total_overtime_minutes": agg["total_overtime_minutes"],
        "attendance_pct": pct
    }


@app.get("/analytics/departments/summary")
def department_summary(
    month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    department: Optional[str] = None
):
    start_date, end_date = parse_month(month)
    
    match_stage = {"joined_on": {"$lte": end_date.isoformat()}}
    if department:
        match_stage["department"] = department
        
    pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": "$department",
            "headcount": {"$sum": 1},
            "emp_codes": {"$push": "$emp_code"}
        }},
        {"$lookup": {
            "from": "attendance_logs",
            "let": {"codes": "$emp_codes"},
            "pipeline": [
                {"$match": {
                    "$expr": {"$in": ["$emp_code", "$$codes"]},
                    "date": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()}
                }},
                {"$addFields": {
                    "dow": {"$dayOfWeek": {"$dateFromString": {"dateString": "$date"}}}
                }}
            ],
            "as": "logs"
        }},
        {"$unwind": {"path": "$logs", "preserveNullAndEmptyArrays": True}},
        {"$group": {
            "_id": "$_id",
            "headcount": {"$first": "$headcount"},
            "present_days": {
                "$sum": {
                    "$cond": [
                        {"$and": [
                            {"$in": ["$logs.status", list(PRESENCE_STATUS)]},
                            {"$in": ["$logs.dow", [2, 3, 4, 5, 6]]}
                        ]},
                        {"$cond": ["$logs.half_day", 0.5, 1]},
                        0
                    ]
                }
            },
            "wh_sum": {
                "$sum": {
                    "$cond": [
                        {"$and": [
                            {"$in": ["$logs.status", list(PRESENCE_STATUS)]},
                            {"$ne": ["$logs.work_hours", None]}
                        ]},
                        "$logs.work_hours",
                        0
                    ]
                }
            },
            "wh_count": {
                "$sum": {
                    "$cond": [
                        {"$and": [
                            {"$in": ["$logs.status", list(PRESENCE_STATUS)]},
                            {"$ne": ["$logs.work_hours", None]}
                        ]},
                        1,
                        0
                    ]
                }
            },
            "late_count": {
                "$sum": {"$cond": [{"$gt": ["$logs.late_minutes", 0]}, 1, 0]}
            },
            "total_late_minutes": {"$sum": {"$ifNull": ["$logs.late_minutes", 0]}},
            "leave_count": {
                "$sum": {"$cond": [{"$eq": ["$logs.status", "LEAVE"]}, 1, 0]}
            },
            "on_duty_count": {
                "$sum": {"$cond": [{"$eq": ["$logs.status", "ON_DUTY"]}, 1, 0]}
            }
        }},
        {"$sort": {"_id": 1}}
    ]
    
    res = list(db.employees.aggregate(pipeline))
    items = []
    for d in res:
        avg_wh = None
        if d["wh_count"] > 0:
            avg_wh = float(Decimal(d["wh_sum"] / d["wh_count"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        items.append({
            "department": d["_id"],
            "headcount": d["headcount"],
            "present_days": d["present_days"],
            "avg_work_hours": avg_wh,
            "late_count": d["late_count"],
            "total_late_minutes": d["total_late_minutes"],
            "leave_count": d["leave_count"],
            "on_duty_count": d["on_duty_count"]
        })
        
    return {"month": month, "items": items}


@app.get("/analytics/leaderboard/late")
def late_leaderboard(
    month: str = Query(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    limit: int = Query(10, ge=1, le=50),
    department: Optional[str] = None
):
    start_date, end_date = parse_month(month)
    
    pipeline = [
        {"$match": {
            "date": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()},
            "late_minutes": {"$gt": 0}
        }},
        {"$group": {
            "_id": "$emp_code",
            "total_late_minutes": {"$sum": "$late_minutes"},
            "late_count": {"$sum": 1}
        }},
        {"$lookup": {
            "from": "employees",
            "localField": "_id",
            "foreignField": "emp_code",
            "as": "emp"
        }},
        {"$unwind": "$emp"}
    ]
    if department:
        pipeline.append({"$match": {"emp.department": department}})
        
    pipeline.extend([
        {"$setWindowFields": {
            "sortBy": {"total_late_minutes": -1},
            "output": {
                "rank": {"$rank": {}}
            }
        }},
        {"$match": {"rank": {"$lte": limit}}},
        {"$sort": {"total_late_minutes": -1, "_id": 1}},
        {"$project": {
            "_id": 0,
            "rank": 1,
            "emp_code": "$_id",
            "name": "$emp.name",
            "department": "$emp.department",
            "total_late_minutes": 1,
            "late_count": 1
        }}
    ])
    
    res = list(db.attendance_logs.aggregate(pipeline))
    return {"month": month, "items": res}


@app.get("/analytics/departments/{department}/trend")
def department_trend(
    department: str,
    from_date: str = Query(..., alias="from", pattern=r"^\d{4}-\d{2}-\d{2}$"),
    to_date: str = Query(..., alias="to", pattern=r"^\d{4}-\d{2}-\d{2}$")
):
    try:
        f_dt = date_type.fromisoformat(from_date)
        t_dt = date_type.fromisoformat(to_date)
    except ValueError:
        raise HTTPException(422, detail="Invalid dates")
        
    if t_dt < f_dt or (t_dt - f_dt).days > 92:
        raise HTTPException(422, detail="Invalid date range (max 92 days)")

    emp_count = db.employees.count_documents({"department": department})
    if emp_count == 0:
        raise HTTPException(404, detail="Department not found")

    days = (t_dt - f_dt).days
    pipeline = [
        {"$match": {"department": department}},
        {"$group": {
            "_id": None,
            "employees": {"$push": {"emp_code": "$emp_code", "joined_on": "$joined_on"}}
        }},
        {"$addFields": {
            "days_offsets": {"$range": [0, days + 1]}
        }},
        {"$unwind": "$days_offsets"},
        {"$addFields": {
            "date_dt": {"$dateAdd": {
                "startDate": datetime(f_dt.year, f_dt.month, f_dt.day, tzinfo=timezone.utc),
                "unit": "day",
                "amount": "$days_offsets"
            }}
        }},
        {"$addFields": {
            "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$date_dt"}},
            "dow": {"$dayOfWeek": "$date_dt"}
        }},
        {"$addFields": {
            "is_working_day": {"$in": ["$dow", [2, 3, 4, 5, 6]]}
        }},
        {"$addFields": {
            "headcount": {
                "$size": {
                    "$filter": {
                        "input": "$employees",
                        "as": "emp",
                        "cond": {"$lte": ["$$emp.joined_on", "$date"]}
                    }
                }
            }
        }},
        {"$lookup": {
            "from": "attendance_logs",
            "let": {"date": "$date", "emp_codes": "$employees.emp_code"},
            "pipeline": [
                {"$match": {
                    "$expr": {
                        "$and": [
                            {"$eq": ["$date", "$$date"]},
                            {"$in": ["$emp_code", "$$emp_codes"]}
                        ]
                    }
                }}
            ],
            "as": "logs"
        }},
        {"$addFields": {
            "present_count": {
                "$sum": {
                    "$map": {
                        "input": "$logs",
                        "as": "log",
                        "in": {
                            "$cond": [
                                {"$in": ["$$log.status", list(PRESENCE_STATUS)]},
                                {"$cond": ["$$log.half_day", 0.5, 1]},
                                0
                            ]
                        }
                    }
                }
            },
            "late_count": {
                "$size": {
                    "$filter": {
                        "input": "$logs",
                        "as": "log",
                        "cond": {"$gt": ["$$log.late_minutes", 0]}
                    }
                }
            }
        }},
        {"$addFields": {
            "attendance_rate": {
                "$cond": [
                    {"$and": ["$is_working_day", {"$gt": ["$headcount", 0]}]},
                    {"$divide": ["$present_count", "$headcount"]},
                    None
                ]
            }
        }},
        {"$sort": {"date": 1}},
        {"$setWindowFields": {
            "sortBy": {"date": 1},
            "output": {
                "moving_avg_7d": {
                    "$avg": "$attendance_rate",
                    "window": {"documents": [-6, 0]}
                }
            }
        }},
        {"$project": {
            "_id": 0,
            "date": 1,
            "is_working_day": 1,
            "headcount": 1,
            "present_count": 1,
            "late_count": 1,
            "attendance_rate": {
                "$cond": [
                    {"$eq": ["$attendance_rate", None]},
                    None,
                    {"$round": ["$attendance_rate", 4]}
                ]
            },
            "moving_avg_7d": {
                "$cond": [
                    {"$eq": ["$moving_avg_7d", None]},
                    None,
                    {"$round": ["$moving_avg_7d", 4]}
                ]
            }
        }}
    ]

    res = list(db.employees.aggregate(pipeline))
    return {"department": department, "items": res}


@app.get("/admin/explain/{endpoint}")
def explain_endpoint(
    endpoint: str = Path(..., enum=["attendance_list", "employee_monthly", "department_summary", "late_leaderboard", "department_trend"]),
    emp_code: Optional[str] = None,
    month: Optional[str] = None,
    department: Optional[str] = None,
    limit: int = 10,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    page: int = 1,
    page_size: int = 20
):
    if endpoint == "attendance_list":
        q = {}
        if emp_code:
            q["emp_code"] = emp_code
        if date_from or date_to:
            q["date"] = {}
            if date_from:
                q["date"]["$gte"] = date_from
            if date_to:
                q["date"]["$lte"] = date_to
        if status:
            q["status"] = status
        
        cmd = {
            "find": "attendance_logs",
            "filter": q,
            "sort": {"date": -1, "emp_code": 1},
            "skip": (page - 1) * page_size,
            "limit": page_size
        }
        collection = "attendance_logs"

    elif endpoint == "employee_monthly":
        if not emp_code or not month:
            raise HTTPException(422, detail="Missing emp_code or month")
        start_date, end_date = parse_month(month)
        pipeline = [
            {"$match": {
                "emp_code": emp_code,
                "date": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()}
            }}
        ]
        cmd = {"aggregate": "attendance_logs", "pipeline": pipeline, "cursor": {}}
        collection = "attendance_logs"

    elif endpoint == "department_summary":
        if not month:
            raise HTTPException(422, detail="Missing month")
        start_date, end_date = parse_month(month)
        match_stage = {"joined_on": {"$lte": end_date.isoformat()}}
        if department:
            match_stage["department"] = department
        pipeline = [{"$match": match_stage}]
        cmd = {"aggregate": "employees", "pipeline": pipeline, "cursor": {}}
        collection = "employees"

    elif endpoint == "late_leaderboard":
        if not month:
            raise HTTPException(422, detail="Missing month")
        start_date, end_date = parse_month(month)
        match_stage = {
            "date": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()},
            "late_minutes": {"$gt": 0}
        }
        pipeline = [{"$match": match_stage}]
        cmd = {"aggregate": "attendance_logs", "pipeline": pipeline, "cursor": {}}
        collection = "attendance_logs"

    elif endpoint == "department_trend":
        if not department or not from_date or not to_date:
            raise HTTPException(422, detail="Missing department, from, or to")
        pipeline = [{"$match": {"department": department}}]
        cmd = {"aggregate": "employees", "pipeline": pipeline, "cursor": {}}
        collection = "employees"

    explain = db.command("explain", cmd, verbosity="executionStats")
    return {
        "endpoint": endpoint,
        "collection": collection,
        "explain": explain
    }
