from typing import TypedDict
from enum import Enum


class Signal(str, Enum):
    SAFE = "safe"
    WATCH = "watch"
    HOT = "hot"
    DANGER = "danger"


class MarketData(TypedDict):
    date: str
    copper: float
    scco_open: float
    scco_high: float
    scco_low: float
    scco_close: float
    scco_volume: int
    shares: int


class IntradayBar(TypedDict):
    datetime: str
    copper_ref: float
    scco_open: float
    scco_high: float
    scco_low: float
    scco_close: float
    scco_volume: int


class RatioResult(TypedDict):
    ratio: float
    p_safe: float
    p_watch: float
    p_hot: float
