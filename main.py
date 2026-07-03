"""
SCCO Monitor — Cola 铜价系数模型
单文件：采集 → 计算 → CSV 记录 → HTML 图表 → 通知推送
"""

import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
import yfinance as yf

# ── 配置 ──────────────────────────────────────────
COPPER_TICKER = "HG=F"
SCCO_TICKER = "SCCO"
DEFAULT_SHARES = 773_000_000
USER_COST = float(os.getenv("USER_COST", "184.36"))

DATA_DIR = Path("data")
DOCS_DIR = Path("docs")
CSV_PATH = DATA_DIR / "history.csv"
HTML_PATH = DOCS_DIR / "index.html"

FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ── 数据采集 ──────────────────────────────────────
def fetch_market_data() -> dict:
    copper = yf.Ticker(COPPER_TICKER)
    scco = yf.Ticker(SCCO_TICKER)

    copper_hist = copper.history(period="1d")
    scco_hist = scco.history(period="1d")

    if copper_hist.empty or scco_hist.empty:
        print("ERROR: empty data from yfinance")
        sys.exit(1)

    p_copper = copper_hist["Close"].iloc[-1]
    scco_open = scco_hist["Open"].iloc[-1]
    scco_high = scco_hist["High"].iloc[-1]
    scco_low = scco_hist["Low"].iloc[-1]
    scco_close = scco_hist["Close"].iloc[-1]
    scco_volume = scco_hist["Volume"].iloc[-1]

    shares = scco.info.get("sharesOutstanding") or DEFAULT_SHARES

    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "copper": round(float(p_copper), 4),
        "scco_open": round(float(scco_open), 2),
        "scco_high": round(float(scco_high), 2),
        "scco_low": round(float(scco_low), 2),
        "scco_close": round(float(scco_close), 2),
        "scco_volume": int(scco_volume),
        "shares": int(shares),
    }

# ── Cola 计算 ─────────────────────────────────────
def calculate_cola(data: dict) -> dict:
    p_copper = data["copper"]
    p_scco = data["scco_close"]
    shares = data["shares"]

    actual_mcap = p_scco * shares / 1e8  # 亿
    anchor_mcap = p_copper / 4.2 * 900   # 亿 (900亿 = 9e10)
    ratio = actual_mcap / anchor_mcap

    p_110 = 1.10 * anchor_mcap * 1e8 / shares
    p_120 = 1.20 * anchor_mcap * 1e8 / shares
    p_150 = 1.50 * anchor_mcap * 1e8 / shares

    return {
        "ratio": round(ratio, 4),
        "p_110": round(p_110, 2),
        "p_120": round(p_120, 2),
        "p_150": round(p_150, 2),
    }

# ── 信号判定 ──────────────────────────────────────
def get_signal(ratio: float) -> tuple:
    keys = "safe", "安全", "🟢 偏安全", "逢低分批买入，无需因估值砍仓"
    if 1.10 < ratio <= 1.20:
        keys = "watch", "合理", "🟡 合理区间", "持有观望，不盲目追高"
    elif 1.20 < ratio < 1.50:
        keys = "hot", "偏热", "🟠 偏热", "停止加仓，逐步降 Beta"
    elif ratio >= 1.50:
        keys = "danger", "减仓", "🔴 减仓区", "分批减仓，严控风险"
    return keys

# ── CSV 读写 ──────────────────────────────────────
FIELDS = [
    "date", "copper",
    "scco_open", "scco_high", "scco_low", "scco_close", "scco_volume",
    "ratio", "p_110", "p_120", "p_150",
]

def _merge_row(existing: list[dict], new_row: dict) -> list[dict]:
    seen = False
    out = []
    for r in existing:
        if r["date"] == new_row["date"]:
            out.append(new_row)
            seen = True
        else:
            out.append(r)
    if not seen:
        out.append(new_row)
    out.sort(key=lambda r: r["date"])
    return out

def append_csv(data: dict, cola: dict):
    DATA_DIR.mkdir(exist_ok=True)
    new_row = {k: data.get(k) or cola.get(k) for k in FIELDS}
    if not CSV_PATH.exists():
        with open(CSV_PATH, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerow(new_row)
        return

    with open(CSV_PATH) as f:
        existing = list(csv.DictReader(f))
    merged = _merge_row(existing, new_row)
    with open(CSV_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(merged)

def read_csv() -> list[dict]:
    if not CSV_PATH.exists():
        return []
    with open(CSV_PATH) as f:
        return list(csv.DictReader(f))

# ── HTML 生成 ─────────────────────────────────────
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SCCO · Cola Monitor</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0f0f1a;color:#c8c8d4;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;padding:24px}
.container{max-width:1100px;margin:0 auto}
h1{font-size:20px;font-weight:600;color:#e8e8f0;margin-bottom:4px}
.sub{font-size:13px;color:#888}
.card{background:#1a1a2e;border-radius:12px;padding:20px;margin:16px 0}
.card-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-top:12px}
.stat-label{font-size:11px;text-transform:uppercase;color:#666;letter-spacing:.5px}
.stat-value{font-size:22px;font-weight:700;margin-top:2px}
.stat-value.safe{color:#22c55e}
.stat-value.watch{color:#eab308}
.stat-value.hot{color:#f97316}
.stat-value.danger{color:#ef4444}
.signal{font-size:15px;font-weight:600;margin-top:4px}
.advice{font-size:13px;color:#888;margin-top:2px}
.tag{display:inline-block;padding:2px 10px;border-radius:6px;font-size:12px;font-weight:600}
.tag.safe{background:#22c55e20;color:#22c55e;border:1px solid #22c55e40}
.tag.watch{background:#eab30820;color:#eab308;border:1px solid #eab30840}
.tag.hot{background:#f9731620;color:#f97316;border:1px solid #f9731640}
.tag.danger{background:#ef444420;color:#ef4444;border:1px solid #ef444440}
#chart{height:600px;margin-top:16px}
.footer{text-align:center;font-size:12px;color:#555;margin-top:24px}
.empty-state{text-align:center;padding:80px 20px;color:#555}
.empty-state p{font-size:16px;margin-top:8px}
</style>
</head>
<body>
<div class="container">
<h1>SCCO · Cola 铜价系数监控</h1>
<p class="sub">%s</p>
%s
</div>
<script>
%s
</script>
</body>
</html>"""

STATUS_BAR = """<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <span class="tag %s">%s</span>
      <div class="signal">%s</div>
      <div class="advice">%s</div>
    </div>
    <div style="text-align:right">
      <div class="stat-label">当前系数</div>
      <div class="stat-value %s">%.4f</div>
    </div>
  </div>
  <div class="card-grid">
    <div><div class="stat-label">铜价</div><div class="stat-value">$%.4f</div></div>
    <div><div class="stat-label">SCCO</div><div class="stat-value">$%.2f</div></div>
    <div><div class="stat-label">P 1.10</div><div class="stat-value" style="color:#22c55e">$%.2f</div></div>
    <div><div class="stat-label">P 1.20</div><div class="stat-value" style="color:#eab308">$%.2f</div></div>
    <div><div class="stat-label">P 1.50</div><div class="stat-value" style="color:#ef4444">$%.2f</div></div>
  </div>
</div>
<div id="chart"></div>
<div class="footer">数据来源: Yahoo Finance · 每交易日更新 · <a href="https://github.com/yang-xianfeng/scco-monitor" style="color:#555">GitHub</a></div>"""

CHART_SCRIPT = """const DATA = %s;
if (DATA.length === 0) {
  document.getElementById('chart').innerHTML = '<div class="empty-state"><h2>暂无数据</h2><p>等待首次采集完成后将显示 K 线图</p></div>';
} else {
  const dates = DATA.map(r=>r.date);
  Plotly.newPlot('chart', [
    {type:'candlestick', x:dates, open:DATA.map(r=>+r.scco_open), high:DATA.map(r=>+r.scco_high), low:DATA.map(r=>+r.scco_low), close:DATA.map(r=>+r.scco_close), name:'SCCO', increasing:{line:{color:'#22c55e'}}, decreasing:{line:{color:'#ef4444'}}},
    {type:'scatter', x:dates, y:DATA.map(r=>+r.p_110), name:'P 1.10 (安全上沿)', line:{color:'#22c55e',dash:'dash',width:1}},
    {type:'scatter', x:dates, y:DATA.map(r=>+r.p_120), name:'P 1.20 (合理上沿)', line:{color:'#eab308',dash:'dash',width:1}},
    {type:'scatter', x:dates, y:DATA.map(r=>+r.p_150), name:'P 1.50 (减仓起点)', line:{color:'#ef4444',dash:'dash',width:1}},
  ], {
    paper_bgcolor:'#1a1a2e', plot_bgcolor:'#1a1a2e',
    font:{color:'#c8c8d4',size:12},
    xaxis:{gridcolor:'#2a2a3e',rangeslider:{visible:false},type:'date'},
    yaxis:{gridcolor:'#2a2a3e',title:'价格 (USD)',side:'right'},
    margin:{l:60,r:60,t:20,b:40},
    legend:{orientation:'h',y:1.08,x:0,font:{size:11}},
    hovermode:'x unified',
  }, {responsive:true,displayModeBar:false});
}"""

def build_html(rows: list[dict], data: dict, cola: dict):
    DOCS_DIR.mkdir(exist_ok=True)
    signal_name, tag, signal_label, advice = get_signal(cola["ratio"])
    updated = datetime.now().strftime("%Y-%m-%d %H:%M UTC")

    status_bar = STATUS_BAR % (
        signal_name, tag,
        signal_label, advice,
        signal_name, cola["ratio"],
        data["copper"], data["scco_close"],
        cola["p_110"], cola["p_120"], cola["p_150"],
    ) if rows else ""

    chart_data = json.dumps(rows, ensure_ascii=False)
    chart_script = CHART_SCRIPT % chart_data

    html = HTML_TEMPLATE % (
        f"更新于 {updated}  ·  共 {len(rows)} 个交易日数据",
        status_bar,
        chart_script,
    )
    HTML_PATH.write_text(html, encoding="utf-8")

# ── 通知推送 ──────────────────────────────────────
def push_notification(text: str):
    if FEISHU_WEBHOOK:
        try:
            requests.post(FEISHU_WEBHOOK, json={"msg_type": "text", "content": {"text": text}}, timeout=10)
        except Exception as e:
            print(f"WARN: feishu push failed: {e}")
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        try:
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10)
        except Exception as e:
            print(f"WARN: telegram push failed: {e}")

# ── 主入口 ────────────────────────────────────────
def main():
    print("=== SCCO Monitor ===")

    data = fetch_market_data()
    print(f"  Copper: ${data['copper']}  SCCO: ${data['scco_close']}")

    cola = calculate_cola(data)
    print(f"  Ratio: {cola['ratio']}  |  P_110: {cola['p_110']}  P_120: {cola['p_120']}  P_150: {cola['p_150']}")

    append_csv(data, cola)
    print("  CSV updated")

    rows = read_csv()
    build_html(rows, data, cola)
    print(f"  HTML generated ({len(rows)} rows)")

    signal_name, tag, signal_label, advice = get_signal(cola["ratio"])
    pl_pct = (data["scco_close"] - USER_COST) / USER_COST * 100

    report = (
        f"【SCCO Monitor】{datetime.now().strftime('%m-%d %H:%M')}\n"
        f"铜价 ${data['copper']}  |  SCCO ${data['scco_close']} ({pl_pct:+.1f}%)\n"
        f"系数 {cola['ratio']}  |  {signal_label}\n"
        f"{advice}"
    )
    print(report)
    push_notification(report)
    print("=== Done ===")

if __name__ == "__main__":
    main()
