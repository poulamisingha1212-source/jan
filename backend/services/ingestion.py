"""
Prototype data pipeline — static sample dataset only.

There is NO network ingestion in prototype mode. The configured local snapshot
is reshaped into work-level facts, scored with the multi-agent risk system
(model/agents/), and upserted into the database. Every load appends exactly
one sync_logs entry with its snapshot provenance label.

The old live portal fetch (backend/services/mplads_live.py) is legacy code
kept for the future production integration — nothing imports it here.
"""
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from backend.database import SessionLocal, run_lightweight_migrations
from backend.models import Work, SyncLog, MPAllocation
from backend.config import settings
from model.risk_engine import score_dataset

# Canonical source label used across the status UI
SOURCE_LABEL = "Prototype Sample Dataset (MPLADS portal export)"
LIVE_CACHE_LABEL = "Cached MPLADS Portal Snapshot (offline export)"

_UPSERT_CHUNK = 900  # stay under SQLite's 999 bind-parameter limit


# ------------------------------------------------------------------------------
# Normalization & scoring
# ------------------------------------------------------------------------------

def load_sample_dataframe() -> pd.DataFrame:
    """Read the configured local MPLADS snapshot."""
    return pd.read_csv(settings.SAMPLE_DATA_PATH)


def source_label_for(path: Path) -> str:
    """Return a provenance label for a local snapshot file."""
    return LIVE_CACHE_LABEL if path.resolve() == settings.LIVE_CACHE_PATH.resolve() else SOURCE_LABEL


def _reshape_long_format(df: pd.DataFrame) -> pd.DataFrame:
    """Convert the portal's long format (record_type rows) into work-level facts."""
    if "record_type" not in df.columns:
        if "total_fund_disbursed" not in df.columns:
            df["total_fund_disbursed"] = 0.0
        return df

    sanctioned = df[df["record_type"] == "Works Sanctioned"].copy()
    if len(sanctioned) == 0:
        sanctioned = df.dropna(subset=["work_id"]).drop_duplicates("work_id").copy()
    else:
        sanctioned = sanctioned.drop_duplicates("work_id")

    completed = df[df["record_type"] == "Works Completed"].copy()
    expenditure = df[df["record_type"] == "Expenditure on Completed & On-going Works"].copy()

    if len(expenditure) > 0 and "fund_disbursed_amount" in expenditure.columns:
        expenditure["fund_disbursed_amount"] = pd.to_numeric(
            expenditure["fund_disbursed_amount"], errors="coerce"
        ).fillna(0)
        # Rich per-work payment aggregates power the vendor, stall and
        # post-completion billing signals used by the risk agents.
        exp_agg = expenditure.groupby("work_id").agg(
            total_fund_disbursed=("fund_disbursed_amount", "sum"),
            n_vendor_payments=("fund_disbursed_amount", "count"),
            primary_vendor=("vendor_name", lambda s: s.dropna().mode().iat[0] if not s.dropna().mode().empty else None),
            last_expenditure_date=("expenditure_date", lambda s: s.dropna().max() if s.notna().any() else None),
            payment_statuses=("payment_status", lambda s: "|".join(sorted({str(x) for x in s.dropna()}))),
        ).reset_index()
        exp_agg["n_distinct_vendors"] = expenditure.dropna(subset=["vendor_name"]).groupby("work_id")["vendor_name"].nunique()
        sanctioned = sanctioned.merge(exp_agg, on="work_id", how="left")

    if len(completed) > 0 and "amount_disbursed" in completed.columns:
        comp_slim = completed[["work_id", "completion_date", "amount_disbursed"]].dropna(
            subset=["work_id"]
        ).drop_duplicates("work_id")
        sanctioned = sanctioned.merge(comp_slim, on="work_id", how="left", suffixes=("", "_comp"))
        # Sanctioned rows carry empty completion_date/amount_disbursed columns, so
        # the merged values land in *_comp — coalesce them back into the real ones.
        for col in ("completion_date", "amount_disbursed"):
            comp_col = f"{col}_comp"
            if comp_col in sanctioned.columns:
                sanctioned[col] = sanctioned[col].where(sanctioned[col].notna(), sanctioned[comp_col])
                sanctioned.drop(columns=[comp_col], inplace=True)

    if "total_fund_disbursed" not in sanctioned.columns:
        sanctioned["total_fund_disbursed"] = 0.0
    sanctioned["total_fund_disbursed"] = sanctioned["total_fund_disbursed"].fillna(0.0)
    return sanctioned


def _normalize_work(row: pd.Series) -> dict:
    """Map any scored row into the Work table schema (used for bulk mappings)."""
    def _s(key, default=None):
        val = row.get(key)
        return None if pd.isna(val) else str(val)

    def _f(key, default=0.0):
        val = row.get(key, default)
        try:
            return float(default if pd.isna(val) else val)
        except (TypeError, ValueError):
            return float(default)

    flags = row.get("rule_flags_triggered", "[]")
    if isinstance(flags, (list, tuple)):
        flags = str(list(flags))

    # House: taken from the feed when present; otherwise inferred from the
    # constituency (Rajya Sabha members sit for 'Sitting Rajya Sabha').
    house = _s("house")
    if not house:
        constituency = str(row.get("constituency") or "").lower()
        house = "Rajya Sabha" if "rajya sabha" in constituency else "Lok Sabha"

    # CSV round-trips can turn numeric work IDs into '1000.0' — strip it
    work_id = str(row["work_id"])
    if work_id.endswith(".0"):
        work_id = work_id[:-2]

    return {
        "work_id": work_id,
        "mp_name": _s("mp_name"),
        "state": _s("state"),
        "constituency": _s("constituency"),
        "house": house,
        "ida": _s("ida"),
        "primary_vendor": _s("primary_vendor"),
        "work_category": _s("work_category"),
        "work_type": _s("work_type"),
        "sanction_amount": _f("sanction_amount"),
        "total_fund_disbursed": _f("total_fund_disbursed"),
        "utilization_ratio": _f("utilization_ratio"),
        "work_status": _s("work_status"),
        "completion_date": _s("completion_date"),
        "final_risk_score": _f("final_risk_score"),
        "priority_rank": int(_f("priority_rank", 999999)),
        "risk_tier": _s("risk_tier") or "Low Risk",
        "recommended_action": _s("recommended_action") or "Routine monitoring",
        "rule_flag_count": int(_f("rule_flag_count")),
        "rule_flags_triggered": flags,
        "agent_breakdown": _s("agent_breakdown"),
        "likelihood_score": _f("likelihood_score"),
        "impact_score": _f("impact_score"),
        "weighted_rule_score": _f("weighted_rule_score"),
        "anomaly_percentile": _f("anomaly_percentile"),
        "is_anomaly": bool(row.get("is_anomaly", False)),
    }


def _upsert_dataframe(db, df: pd.DataFrame) -> dict:
    """Chunked bulk upsert — one round-trip per ~900 rows, not per row."""
    inserted = updated = 0
    now = datetime.now(timezone.utc)
    rows = [r for _, r in df.iterrows() if not pd.isna(r.get("work_id"))]

    for start in range(0, len(rows), _UPSERT_CHUNK):
        chunk = rows[start:start + _UPSERT_CHUNK]
        mappings = [_normalize_work(r) for r in chunk]
        ids = [m["work_id"] for m in mappings]

        existing_ids = {
            w[0]
            for w in db.query(Work.work_id).filter(Work.work_id.in_(ids)).all()
        }

        new_mappings, upd_mappings = [], []
        for m in mappings:
            if m["work_id"] in existing_ids:
                upd_mappings.append(m)
            else:
                m["created_at"] = now
                new_mappings.append(m)

        if new_mappings:
            db.bulk_insert_mappings(Work, new_mappings)
            inserted += len(new_mappings)
        if upd_mappings:
            for m in upd_mappings:
                m["updated_at"] = now
            db.bulk_update_mappings(Work, upd_mappings)
            updated += len(upd_mappings)
        db.commit()

    return {"inserted": inserted, "updated": updated, "processed": len(rows)}


def _upsert_allocations(db, long_df: pd.DataFrame) -> int:
    """Upsert the per-MP allocated funds from the sample's Allocated Limit
    dataset into mp_allocations, keyed on (mp_name, house, constituency, state)."""
    alloc = long_df[long_df.get("record_type") == "MP Allocated Limit"]
    if alloc.empty:
        return 0
    count = 0
    for _, r in alloc.iterrows():
        if pd.isna(r.get("mp_name")):
            continue
        key = dict(
            mp_name=str(r["mp_name"]),
            house=str(r.get("house") or ("Rajya Sabha" if "rajya sabha" in str(r.get("constituency") or "").lower() else "Lok Sabha")),
            constituency=str(r.get("constituency") or ""),
            state=str(r.get("state") or ""),
        )
        values = dict(
            allocated_amount=float(r.get("allocated_amount") or 0),
            tenure_start=str(r.get("recommended_date")) if pd.notna(r.get("recommended_date")) else None,
            updated_at=datetime.now(timezone.utc),
        )
        row = db.query(MPAllocation).filter_by(**key).one_or_none()
        if row:
            for k, v in values.items():
                setattr(row, k, v)
        else:
            db.add(MPAllocation(**key, **values))
        count += 1
    db.commit()
    return count


def _log_sync(db, *, source, status, start_dt, counts=None, note=None):
    end_dt = datetime.now(timezone.utc)
    counts = counts or {}
    db.add(SyncLog(
        run_timestamp=start_dt,
        start_time=start_dt,
        end_time=end_dt,
        status=status,
        source=source,
        rows_fetched=counts.get("fetched", 0),
        rows_processed=counts.get("processed", 0),
        rows_inserted=counts.get("inserted", 0),
        rows_updated=counts.get("updated", 0),
        rows_rejected=counts.get("rejected", 0),
        error_message=note,
    ))
    db.commit()


# ------------------------------------------------------------------------------
# Public entry points
# ------------------------------------------------------------------------------

def run_ingestion(source_file_path: Path = None) -> dict:
    """
    Load the prototype sample dataset: reshape → multi-agent risk score → upsert.
    Writes exactly one sync_logs entry. No network access, no scheduler.
    """
    start_dt = datetime.now(timezone.utc)
    t0 = time.time()
    run_lightweight_migrations()
    db = SessionLocal()

    try:
        if source_file_path is not None:
            df = pd.read_csv(source_file_path, low_memory=False)
        else:
            df = load_sample_dataframe()

        source_path = Path(source_file_path) if source_file_path is not None else settings.SAMPLE_DATA_PATH
        alloc_rows = df[df.get("record_type") == "MP Allocated Limit"] if "record_type" in df else pd.DataFrame()
        alloc_map = {
            str(row.mp_name): float(row.allocated_amount or 0)
            for row in alloc_rows.itertuples()
            if getattr(row, "mp_name", None) and pd.notna(getattr(row, "allocated_amount", None))
        }
        if not alloc_map:
            alloc_map = {a.mp_name: a.allocated_amount for a in db.query(MPAllocation).all()}
        scored = score_dataset(_reshape_long_format(df.copy()),
                               mp_allocations=alloc_map)
        counts = _upsert_dataframe(db, scored)
        counts["allocations"] = _upsert_allocations(db, df)
        counts["fetched"] = len(df)
        db.commit()
        source_label = source_label_for(source_path)
        _log_sync(db, source=source_label, status="success",
                  start_dt=start_dt, counts=counts)
        return {"status": "success", "mode": "prototype", "source": source_label,
                "duration_seconds": round(time.time() - t0, 2), **counts}
    except Exception as e:
        db.rollback()
        _log_sync(db, source=source_label_for(Path(source_file_path) if source_file_path else settings.SAMPLE_DATA_PATH), status="failed",
                  start_dt=start_dt, note=str(e))
        raise
    finally:
        db.close()


def get_sync_status() -> dict:
    """Prototype status: the dataset is static, so it can never go stale."""
    db = SessionLocal()
    try:
        last_load = db.query(SyncLog).order_by(SyncLog.run_timestamp.desc()).first()
        message = (
            "Prototype mode — static sample dataset from the MPLADS portal. "
            "No live sync is scheduled."
        )
        if not last_load:
            return {
                "latest_sync_timestamp": None,
                "latest_sync_status": "none",
                "is_data_stale": False,
                "staleness_message": "Sample dataset not loaded yet — restart the backend to seed it.",
                "rows_processed": 0,
                "mode": "prototype",
            }

        loaded_at = last_load.run_timestamp.isoformat() if last_load.run_timestamp else None
        if last_load.status != "success":
            message = f"Sample load reported: {last_load.error_message or last_load.status}"

        return {
            "latest_sync_timestamp": loaded_at,
            "latest_sync_status": last_load.status,
            "latest_sync_source": last_load.source,
            "is_data_stale": False,
            "staleness_message": message,
            "rows_processed": last_load.rows_processed,
            "source": last_load.source,
            "error_message": last_load.error_message,
            "mode": "prototype",
        }
    finally:
        db.close()
