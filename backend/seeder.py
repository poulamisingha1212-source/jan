"""
Database bootstrap for the prototype: the works table is seeded from the
bundled MPLADS sample export (data/mplads_raw_sample.csv) when empty.
Idempotent — repeated starts never duplicate or overwrite existing rows.
"""
import argparse
from pathlib import Path

from sqlalchemy import func

from backend.database import SessionLocal, engine, Base, run_lightweight_migrations
from backend.models import Work, ReviewLog, SyncLog, MPAllocation
from backend.config import settings


def seed_database(force: bool = False, source_file_path=None) -> int:
    """
    Ensure tables exist and, when the works table is empty, load and score
    the static sample dataset synchronously (it is small — a few seconds).
    Safe to run repeatedly.
    """
    Base.metadata.create_all(bind=engine)
    run_lightweight_migrations()

    db = SessionLocal()
    try:
        existing_count = db.query(func.count(Work.work_id)).scalar()
        if force and existing_count:
            print(f"Rebuilding prototype database: removing {existing_count} existing works...")
            db.query(ReviewLog).delete(synchronize_session=False)
            db.query(Work).delete(synchronize_session=False)
            db.query(MPAllocation).delete(synchronize_session=False)
            db.query(SyncLog).delete(synchronize_session=False)
            db.commit()
            existing_count = 0
    finally:
        db.close()

    if existing_count and existing_count > 0 and not force:
        print(f"Database already contains {existing_count} records. Prototype seed skipped.")
        return existing_count

    source_path = source_file_path or settings.SAMPLE_DATA_PATH
    print(f"Seeding from dataset {Path(source_path).name}...")
    from backend.services.ingestion import run_ingestion
    result = run_ingestion(source_file_path=source_file_path)
    print(f"Prototype seed finished: {result.get('processed', 0)} works scored "
          f"({result.get('inserted', 0)} inserted) in {result.get('duration_seconds', 0)}s.")
    return result.get("inserted", 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load the static MPLADS prototype dataset.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Clear prototype tables and rebuild them from the bundled sample.",
    )
    parser.add_argument(
        "--source",
        choices=("sample", "live-cache"),
        default="sample",
        help="Local snapshot to load: the small sample or cached portal snapshot.",
    )
    args = parser.parse_args()
    source = settings.SAMPLE_DATA_PATH if args.source == "sample" else settings.LIVE_CACHE_PATH
    if not source.exists():
        parser.error(f"Snapshot not found: {source}")
    seed_database(force=args.force, source_file_path=source)
