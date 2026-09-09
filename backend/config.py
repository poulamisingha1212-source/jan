import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path: Path) -> None:
    """Minimal .env loader — KEY=VALUE lines, no new dependency.
    Existing process env vars always win (setdefault)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_env_file(BASE_DIR / ".env")

class Settings:
    PROJECT_NAME: str = "MPLADS AI Sentinel"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Database URL: PostgreSQL supported; defaults to local SQLite file for development
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        f"sqlite:///{BASE_DIR / 'mplads_sentinel.db'}"
    )
    
    DATA_DIR: Path = BASE_DIR / "data"
    MODEL_DIR: Path = BASE_DIR / "model"
    # Snapshot sources: both are local files; neither performs a network request.
    _configured_dataset_path = Path(os.getenv(
        "MPLADS_DATASET_PATH",
        str(BASE_DIR / "data" / "mplads_raw_sample.csv"),
    ))
    SAMPLE_DATA_PATH: Path = (
        _configured_dataset_path
        if _configured_dataset_path.is_absolute()
        else BASE_DIR / _configured_dataset_path
    )
    LIVE_CACHE_PATH: Path = BASE_DIR / "data" / "last_live_feed.csv"

    CORS_ORIGINS: list = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173,*",
        ).split(",")
        if origin.strip()
    ]

settings = Settings()
