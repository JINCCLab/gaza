from pathlib import Path

from pydantic_settings import BaseSettings


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
EXPORT_DIR = ROOT / "exports"
DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{DATA_DIR / 'data_platform.db'}"
    export_dir: str = str(EXPORT_DIR)
    platform_fee_pct: float = 0.15
    quality_mult_cap: float = 1.5


settings = Settings()
