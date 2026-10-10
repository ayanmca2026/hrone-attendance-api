import os
import pathlib

from bson import json_util
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, DESCENDING

load_dotenv()
here = pathlib.Path(__file__).parent / "sample_data"
opts = json_util.JSONOptions(tz_aware=True)
db = MongoClient(os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017"), tz_aware=True)[os.getenv("MONGO_DB", "hrone_attendance")]

# Create indexes idempotently
db.employees.create_index("emp_code", unique=True)
db.employees.create_index([("department", ASCENDING), ("joined_on", ASCENDING)])
db.attendance_logs.create_index([("emp_code", ASCENDING), ("date", ASCENDING)], unique=True)
db.attendance_logs.create_index([("date", DESCENDING), ("emp_code", ASCENDING)])
db.attendance_logs.create_index([("emp_code", ASCENDING), ("punch_in", DESCENDING)])

for name in ("employees", "attendance_logs"):
    docs = json_util.loads((here / f"{name}.json").read_text(), json_options=opts)
    db[name].delete_many({})
    db[name].insert_many(docs)
    print(f"loaded {len(docs):>2} documents into '{db.name}.{name}' with indexes created.")
