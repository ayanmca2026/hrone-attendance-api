import os
import pathlib
import sys
from bson import json_util
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, DESCENDING

load_dotenv()
here = pathlib.Path(__file__).parent / "sample_data"
opts = json_util.JSONOptions(tz_aware=True)

DISPOSABLE_DB_PATTERNS = ("test", "sample", "dev", "sandbox", "temp", "disposable")


def get_default_db():
    uri = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
    db_name = os.getenv("MONGO_DB", "hrone_attendance")
    client = MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=5000)
    return client[db_name]


def init_indexes(target_db):
    target_db.employees.create_index("emp_code", unique=True)
    target_db.employees.create_index([("department", ASCENDING), ("joined_on", ASCENDING)])
    target_db.attendance_logs.create_index([("emp_code", ASCENDING), ("date", ASCENDING)], unique=True)
    target_db.attendance_logs.create_index([("date", DESCENDING), ("emp_code", ASCENDING)])
    target_db.attendance_logs.create_index([("emp_code", ASCENDING), ("punch_in", DESCENDING)])


def seed_sample_data(target_db=None, reset=False):
    """
    Safely seeds sample data into MongoDB.

    - Default behavior (reset=False): Performs safe, idempotent upserts without deleting
      any existing or unrelated records.
    - Destructive mode (reset=True): Requires explicit opt-in. Refuses to delete data
      on non-disposable databases unless CONFIRM_RESET_DATABASE=yes is set.
    """
    db = target_db if target_db is not None else get_default_db()

    if reset:
        db_name = db.name.lower()
        is_disposable = any(pattern in db_name for pattern in DISPOSABLE_DB_PATTERNS)
        explicit_confirm = os.getenv("CONFIRM_RESET_DATABASE", "").lower() in ("yes", "true", "1")
        if not is_disposable and not explicit_confirm:
            raise RuntimeError(
                f"SAFETY GUARD: Refusing to delete data in non-disposable database '{db.name}'. "
                f"Use a disposable database (e.g. 'hrone_sample', 'hrone_dev') or set CONFIRM_RESET_DATABASE=yes."
            )

    init_indexes(db)

    counts = {}
    for name, key_fields in [
        ("employees", ["emp_code"]),
        ("attendance_logs", ["emp_code", "date"]),
    ]:
        json_file = here / f"{name}.json"
        if not json_file.exists():
            continue
        docs = json_util.loads(json_file.read_text(encoding="utf-8"), json_options=opts)

        if reset:
            db[name].delete_many({})
            if docs:
                db[name].insert_many(docs)
            counts[name] = len(docs)
        else:
            # Safe idempotent upserts without deleting existing unrelated records
            for doc in docs:
                query = {k: doc[k] for k in key_fields}
                db[name].replace_one(query, doc, upsert=True)
            counts[name] = len(docs)

    return counts


if __name__ == "__main__":
    do_reset = "--reset" in sys.argv or os.getenv("ALLOW_DESTRUCTIVE_SEED", "").lower() in ("true", "1", "yes")
    counts = seed_sample_data(reset=do_reset)
    print(f"Seeding completed safely: {counts}")
