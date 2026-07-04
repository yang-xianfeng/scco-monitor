"""SCCO Monitor · 相关性系数 — 主入口.

流程: 回填历史 → 采集 → 计算 → 存储 → 图表 → 通知
"""

from datetime import datetime

from scco_monitor.chart import build_html
from scco_monitor.config import DAYS_HISTORICAL, PAGES_URL
from scco_monitor.core import calculate_ratio, get_signal
from scco_monitor.fetcher import FetchError, fetch_daily_data, fetch_intraday_data, fetch_market_data
from scco_monitor.notifier import push
from scco_monitor.storage import append_csv, read_csv


def _backfill_history() -> list[dict]:
    """回填历史数据到 CSV，只 fetch 不足的部分."""
    rows = read_csv()
    if len(rows) >= DAYS_HISTORICAL:
        return rows
    needed = DAYS_HISTORICAL - len(rows)
    period = f"{needed + 10}d" if needed < 60 else "3mo"
    historical = fetch_daily_data(period=period)
    if not historical:
        return rows
    print(f"  回填 {len(historical)} 日历史数据 (period={period}) ...")
    for h in historical:
        r = calculate_ratio(h)
        append_csv(h, r)
    return read_csv()


def main() -> None:
    now = datetime.now()
    print("=" * 42)
    print("  SCCO Monitor · 相关性系数")
    print(f"  {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 42)

    rows = _backfill_history()
    print(f"\n[1] 历史数据: {len(rows)} 行")

    data = fetch_market_data()
    print(f"[2] 行情: 铜 ${data['copper']}  |  SCCO ${data['scco_close']}")

    intro = fetch_intraday_data()
    print(f"[3] 日内: {len(intro)} 根 15min K 线")

    ratio = calculate_ratio(data)
    sig_key, sig_tag = get_signal(ratio["ratio"])
    print(f"[4] 系数: {ratio['ratio']} ({sig_tag})")

    append_csv(data, ratio)
    rows = read_csv()
    print(f"[5] CSV: {len(rows)} 行")

    build_html(rows, intro, data, ratio)
    print("[6] HTML 已生成")

    report = (
        f"【SCCO Monitor】{now.strftime('%m-%d %H:%M')}\n"
        f"铜 ${data['copper']}  |  SCCO ${data['scco_close']}\n"
        f"系数 {ratio['ratio']}  |  {sig_tag}\n"
        f"📊 {PAGES_URL}"
    )
    print(f"\n{report}\n")
    push(report)

    print("=" * 42)
    print("  ✓ 完成")
    print("=" * 42)


if __name__ == "__main__":
    try:
        main()
    except FetchError as e:
        print(f"ERROR: {e}")
        exit(1)
