import os
import warnings

# Suppress Starlette TestClient deprecation warning regarding httpx
warnings.filterwarnings("ignore", message=".*httpx.*")

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

# Use a specific test database name so we don't accidentally wipe real data
os.environ["MONGO_DB"] = "hrone_attendance_test"

from app.main import app, db, init_indexes

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # Setup indexes
    init_indexes(db)
    yield
    # Cleanup after all tests
    db.employees.drop()
    db.attendance_logs.drop()

@pytest.fixture(autouse=True)
def clear_collections():
    # Run before every test
    db.employees.delete_many({})
    db.attendance_logs.delete_many({})

@pytest.fixture
def client():
    return TestClient(app)
