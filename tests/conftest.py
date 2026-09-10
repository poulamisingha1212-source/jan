import pytest
from backend.database import engine, Base, SessionLocal
from backend.models import Work
from backend.services.ingestion import run_ingestion
from backend.config import settings


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Ensure database schema exists and initial seed data is present for testing."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        count = db.query(Work.work_id).count()
    finally:
        db.close()
    if count == 0:
        run_ingestion(source_file_path=settings.SAMPLE_DATA_PATH)
