from csv import DictReader, DictWriter
from pathlib import Path

from . import config as cfg
from .models import IntradayBar, MarketData, RatioResult

FIELDS = ["date", "copper",
          "scco_open", "scco_high", "scco_low", "scco_close", "scco_volume",
          "ratio", "p_safe", "p_watch", "p_hot"]
INTRADAY_FIELDS = ["datetime", "copper_ref",
                   "scco_open", "scco_high", "scco_low", "scco_close", "scco_volume",
                   "ratio"]


_NUMERIC_KEYS = {"copper", "scco_open", "scco_high", "scco_low", "scco_close", "scco_volume", "shares"}


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def row_to_numeric(row: dict) -> dict:
    """将 CSV 读出的字符串 dict 转为数值类型."""
    out = dict(row)
    for k in _NUMERIC_KEYS:
        if k in out:
            try:
                out[k] = float(out[k])
            except (ValueError, TypeError):
                pass
    if "shares" in out:
        out["shares"] = int(out["shares"])
    return out


def _upsert_rows(existing: list[dict], new_row: dict) -> list[dict]:
    out = [new_row if r["date"] == new_row["date"] else r for r in existing]
    if not any(r["date"] == new_row["date"] for r in existing):
        out.append(new_row)
    out.sort(key=lambda r: r["date"])
    return out


def append_csv(data: MarketData, ratio_result: RatioResult) -> None:
    _ensure_dir(cfg.CSV_PATH)
    merged = {**data, **ratio_result}
    new_row = {k: str(merged[k]) for k in FIELDS}

    if not cfg.CSV_PATH.exists():
        with open(cfg.CSV_PATH, "w", newline="") as f:
            DictWriter(f, fieldnames=FIELDS).writeheader()
            DictWriter(f, fieldnames=FIELDS).writerow(new_row)
        return

    with open(cfg.CSV_PATH) as f:
        existing = list(DictReader(f))
    with open(cfg.CSV_PATH, "w", newline="") as f:
        w = DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(_upsert_rows(existing, new_row))


def read_csv() -> list[MarketData]:
    if not cfg.CSV_PATH.exists():
        return []
    with open(cfg.CSV_PATH) as f:
        return list(DictReader(f))


def append_intraday_csv(rows: list[IntradayBar], ratio: float) -> None:
    _ensure_dir(cfg.CSV_INTRADAY_PATH)
    write_header = not cfg.CSV_INTRADAY_PATH.exists()
    with open(cfg.CSV_INTRADAY_PATH, "a", newline="") as f:
        w = DictWriter(f, fieldnames=INTRADAY_FIELDS)
        if write_header:
            w.writeheader()
        for row in rows:
            w.writerow({
                "datetime": row["datetime"],
                "copper_ref": row.get("copper_ref", ""),
                "scco_open": row["scco_open"],
                "scco_high": row["scco_high"],
                "scco_low": row["scco_low"],
                "scco_close": row["scco_close"],
                "scco_volume": row["scco_volume"],
                "ratio": round(ratio, 4) if ratio else "",
            })


def read_intraday_csv() -> list[dict]:
    if not cfg.CSV_INTRADAY_PATH.exists():
        return []
    with open(cfg.CSV_INTRADAY_PATH) as f:
        return list(DictReader(f))
