from .config import (
    ANCHOR_COPPER_BASE,
    ANCHOR_MCAP_FACTOR,
    ANCHOR_MCAP_UNIT,
    THRESHOLD_HOT,
    THRESHOLD_SAFE,
    THRESHOLD_WATCH,
)
from .models import RatioResult, Signal


def _anchor_mcap(p_copper: float) -> float:
    return p_copper / ANCHOR_COPPER_BASE * ANCHOR_MCAP_FACTOR * ANCHOR_MCAP_UNIT


def calculate_ratio(data: dict) -> RatioResult:
    anchor = _anchor_mcap(float(data["copper"]))
    actual = float(data["scco_close"]) * float(data["shares"])
    ratio = actual / anchor

    return RatioResult(
        ratio=round(ratio, 4),
        p_safe=round(THRESHOLD_SAFE * anchor / float(data["shares"]), 2),
        p_watch=round(THRESHOLD_WATCH * anchor / float(data["shares"]), 2),
        p_hot=round(THRESHOLD_HOT * anchor / float(data["shares"]), 2),
    )


def get_signal(ratio: float) -> tuple[Signal, str]:
    if ratio <= THRESHOLD_SAFE:
        return Signal.SAFE, "安全"
    if ratio <= THRESHOLD_WATCH:
        return Signal.WATCH, "关注"
    if ratio < THRESHOLD_HOT:
        return Signal.HOT, "偏热"
    return Signal.DANGER, "过热"
