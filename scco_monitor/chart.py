"""HTML 图表 — 相关性系数监控面板.

Plotly 深色主题, 包含:
  1. 信号卡片 + 系数展示
  2. 价格指标网格
  3. 组合 K 线 (60 日日线 + 当日 15min 日内)
  4. 系数区间历史回放 + 资金曲线
"""

import json
from datetime import datetime

from .config import (
    ANCHOR_COPPER_BASE,
    ANCHOR_MCAP_FACTOR,
    DAYS_HISTORICAL,
    GITHUB_REPOSITORY,
    PAGES_URL,
    THRESHOLD_HOT,
    THRESHOLD_SAFE,
    THRESHOLD_WATCH,
)
from .core import get_signal


def build_chart_json(daily, intraday, backtest, cur_data, cur_ratio) -> str:
    """构建 Plotly 图表配置."""
    daily_slice = daily[-DAYS_HISTORICAL:] if len(daily) > DAYS_HISTORICAL else daily

    dates, opn, high, low, close, vol = [], [], [], [], [], []
    p_safe, p_watch, p_hot = [], [], []

    for r in daily_slice:
        dates.append(r["date"] + "T16:00:00")
        opn.append(float(r["scco_open"]))
        high.append(float(r["scco_high"]))
        low.append(float(r["scco_low"]))
        close.append(float(r["scco_close"]))
        vol.append(float(r["scco_volume"]) / 1_000)

        c = float(r["copper"])
        s = float(r.get("shares", 773_000_000) or 773_000_000)
        anchor = c / ANCHOR_COPPER_BASE * ANCHOR_MCAP_FACTOR * 1e8
        p_safe.append(round(THRESHOLD_SAFE * anchor / s, 2))
        p_watch.append(round(THRESHOLD_WATCH * anchor / s, 2))
        p_hot.append(round(THRESHOLD_HOT * anchor / s, 2))

    i_start = len(dates)
    for r in intraday:
        dates.append(r["datetime"])
        opn.append(float(r["scco_open"]))
        high.append(float(r["scco_high"]))
        low.append(float(r["scco_low"]))
        close.append(float(r["scco_close"]))
        vol.append(float(r["scco_volume"]) / 1_000)

        ref = float(r.get("copper_ref", cur_data["copper"]) or cur_data["copper"])
        s = float(cur_data.get("shares", 773_000_000) or 773_000_000)
        anchor = ref / ANCHOR_COPPER_BASE * ANCHOR_MCAP_FACTOR * 1e8
        p_safe.append(round(THRESHOLD_SAFE * anchor / s, 2))
        p_watch.append(round(THRESHOLD_WATCH * anchor / s, 2))
        p_hot.append(round(THRESHOLD_HOT * anchor / s, 2))

    # 系数区间切换标记
    transitions = backtest.get("transitions", [])
    marker_data = {"up": {"x": [], "y": []}, "down": {"x": [], "y": []}}
    for t in transitions:
        dt = t[0] + "T16:00:00"
        key = "up" if t[2] in ("safe", "watch") else "down"
        marker_data[key]["x"].append(dt)
        marker_data[key]["y"].append(t[3])

    data = [
        {"type": "candlestick", "x": dates, "open": opn, "high": high, "low": low,
         "close": close, "name": "SCCO",
         "increasing": {"line": {"color": "#26a69a"}, "fillcolor": "#26a69a"},
         "decreasing": {"line": {"color": "#ef5350"}, "fillcolor": "#ef5350"}},
        {"type": "bar", "x": dates, "y": vol, "name": "成交量 (千股)", "yaxis": "y2",
         "marker": {"color": vol, "colorscale": [[0, "#1a237e"], [1, "#26a69a"]],
                    "showscale": False}, "opacity": 0.4},
    ]

    if p_safe:
        data.append({"type": "scatter", "x": dates, "y": p_safe,
                      "name": f"P<sub>{THRESHOLD_SAFE}</sub> 安全",
                      "line": {"color": "#26a69a", "dash": "dash", "width": 1}})
    if p_watch:
        data.append({"type": "scatter", "x": dates, "y": p_watch,
                      "name": f"P<sub>{THRESHOLD_WATCH}</sub> 关注",
                      "line": {"color": "#ffa726", "dash": "dash", "width": 1}})
    if p_hot:
        data.append({"type": "scatter", "x": dates, "y": p_hot,
                      "name": f"P<sub>{THRESHOLD_HOT}</sub> 偏热",
                      "line": {"color": "#ef5350", "dash": "dash", "width": 1}})

    if marker_data["up"]["x"]:
        data.append({"type": "scatter", "x": marker_data["up"]["x"],
                      "y": marker_data["up"]["y"], "mode": "markers",
                      "name": "区间下移", "marker": {"symbol": "triangle-down",
                      "size": 9, "color": "#26a69a", "line": {"color": "#fff", "width": 1}}})
    if marker_data["down"]["x"]:
        data.append({"type": "scatter", "x": marker_data["down"]["x"],
                      "y": marker_data["down"]["y"], "mode": "markers",
                      "name": "区间上移", "marker": {"symbol": "triangle-up",
                      "size": 9, "color": "#ef5350", "line": {"color": "#fff", "width": 1}}})

    if i_start > 0 and i_start < len(dates):
        y_min = min(low + close) * 0.95 if (low + close) else 100
        y_max = max(high + close) * 1.05 if (high + close) else 300
        data.append({"type": "scatter", "x": [dates[i_start], dates[i_start]],
                      "y": [y_min, y_max], "mode": "lines", "name": "日内",
                      "line": {"color": "#888", "dash": "dot", "width": 1},
                      "hoverinfo": "skip"})

    layout = {
        "paper_bgcolor": "#0d1117", "plot_bgcolor": "#0d1117",
        "font": {"color": "#c9d1d9", "family": "-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif", "size": 11},
        "margin": {"l": 48, "r": 24, "t": 32, "b": 48},
        "xaxis": {"domain": [0, 1], "gridcolor": "#21262d", "zerolinecolor": "#21262d",
                  "type": "date", "rangeslider": {"visible": False}},
        "yaxis": {"domain": [0.25, 1], "gridcolor": "#21262d", "zerolinecolor": "#21262d",
                  "title": "价格 (USD)", "side": "right"},
        "yaxis2": {"domain": [0, 0.2], "gridcolor": "#21262d", "zerolinecolor": "#21262d",
                   "title": "成交量", "side": "right"},
        "legend": {"orientation": "h", "y": 1.02, "x": 0, "font": {"size": 10},
                   "bgcolor": "rgba(0,0,0,0)"},
        "hovermode": "x unified", "dragmode": "zoom",
    }
    return json.dumps({"data": data, "layout": layout, "config": {"responsive": True, "displayModeBar": False, "scrollZoom": True}},
                       ensure_ascii=False, default=str)


def build_bt_chart_json(backtest: dict, cur_price: float) -> str:
    """构建回测-系数区间资金曲线图."""
    zones = backtest.get("zone_history", [])
    if len(zones) < 2:
        return "null"

    dates = [z[0] + "T16:00:00" for z in zones]
    ratios = [z[2] for z in zones]
    prices = [z[3] for z in zones]
    zone_colors = {"safe": "#26a69a", "watch": "#ffa726", "hot": "#ff7043", "danger": "#ef5350"}

    # 当前价格锚定
    nav = [p / cur_price * 100 for p in prices]  # 归一化到当前价格=100

    trace = {
        "type": "scatter", "x": dates, "y": ratios,
        "mode": "lines+markers",
        "name": "相关性系数",
        "line": {"color": "#58a6ff", "width": 2},
        "marker": {"color": [zone_colors.get(z[1], "#888") for z in zones],
                   "size": 4},
        "hovertemplate": "%{x}<br>系数: %{y:.4f}<br>价格: $%{customdata:.2f}<extra></extra>",
        "customdata": prices,
    }

    shapes = []
    for i in range(len(dates) - 1):
        z = zones[i][1]
        shapes.append({
            "type": "rect", "xref": "x", "yref": "paper",
            "x0": dates[i], "x1": dates[i + 1],
            "y0": 0, "y1": 1,
            "fillcolor": zone_colors.get(z, "#888"),
            "opacity": 0.06, "line": {"width": 0},
            "layer": "below",
        })

    layout = {
        "paper_bgcolor": "#161b22", "plot_bgcolor": "#161b22",
        "font": {"color": "#8b949e", "size": 10},
        "margin": {"l": 50, "r": 16, "t": 8, "b": 24},
        "xaxis": {"gridcolor": "#21262d", "zerolinecolor": "#21262d", "type": "date"},
        "yaxis": {"gridcolor": "#21262d", "zerolinecolor": "#21262d",
                  "title": "系数", "side": "right"},
        "hovermode": "x", "showlegend": False,
        "shapes": shapes,
    }
    return json.dumps({"data": [trace], "layout": layout, "config": {"responsive": True, "displayModeBar": False}},
                       ensure_ascii=False, default=str)


def build_html(daily, intraday, cur_data, cur_ratio, backtest) -> None:
    """生成完整 HTML."""
    from pathlib import Path
    from .config import DOCS_DIR, HTML_PATH
    Path(DOCS_DIR).mkdir(exist_ok=True)

    sig_key, sig_tag = get_signal(cur_ratio["ratio"])
    now = datetime.now()

    chart_json = build_chart_json(daily, intraday, backtest, cur_data, cur_ratio)
    bt_chart_json = build_bt_chart_json(backtest, cur_data["scco_close"])

    total_days = len(daily)
    transitions = backtest.get("transitions", [])
    zones = backtest.get("zone_history", [])

    html = _TEMPLATE % {
        "updated": now.strftime("%Y-%m-%d %H:%M UTC"),
        "total_days": total_days,
        "sig_key": sig_key,
        "sig_tag": sig_tag,
        "ratio": cur_ratio["ratio"],
        "copper": cur_data["copper"],
        "scco_close": cur_data["scco_close"],
        "p_safe": cur_ratio["p_safe"],
        "p_watch": cur_ratio["p_watch"],
        "p_hot": cur_ratio["p_hot"],
        "chart_json": chart_json,
        "bt_chart_json": bt_chart_json,
        "transitions": len(transitions),
        "zones_count": len(zones),
        "github_url": f"https://github.com/{GITHUB_REPOSITORY}",
        "pages_url": PAGES_URL,
    }
    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"  HTML 生成 ({total_days} 日 + {len(intraday)} 根日内)")


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SCCO · 相关性系数</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
:root{--bg:#0d1117;--card:#161b22;--border:#30363d;--text:#c9d1d9;--sec:#8b949e;--muted:#484f58;--safe:#26a69a;--watch:#ffa726;--hot:#ff7043;--danger:#ef5350;--accent:#58a6ff;--font:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
*{margin:0;padding:0;box-sizing:border-box}
html{font-size:14px}
body{background:var(--bg);color:var(--text);font-family:var(--font);line-height:1.5}
.container{max-width:1200px;margin:0 auto;padding:20px 16px}
.header{display:flex;justify-content:space-between;align-items:center;padding:0 0 16px;border-bottom:1px solid var(--border);margin-bottom:16px}
.header h1{font-size:18px;font-weight:600}
.header h1 span{color:var(--sec);font-weight:400}
.header-meta{text-align:right;font-size:11px;color:var(--sec)}
.signal-row{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
.card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:18px;position:relative;overflow:hidden}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px}
.card.safe::before{background:var(--safe)}
.card.watch::before{background:var(--watch)}
.card.hot::before{background:var(--hot)}
.card.danger::before{background:var(--danger)}
.tag{display:inline-block;padding:2px 10px;border-radius:4px;font-size:11px;font-weight:600}
.tag.safe{background:rgba(38,166,154,.15);color:var(--safe);border:1px solid rgba(38,166,154,.3)}
.tag.watch{background:rgba(255,167,38,.15);color:var(--watch);border:1px solid rgba(255,167,38,.3)}
.tag.hot{background:rgba(255,112,67,.15);color:var(--hot);border:1px solid rgba(255,112,67,.3)}
.tag.danger{background:rgba(239,83,80,.15);color:var(--danger);border:1px solid rgba(239,83,80,.3)}
.signal-label{font-size:15px;font-weight:600;margin:6px 0 0}
.coef-wrap{text-align:right}
.coef-wrap .label{font-size:10px;text-transform:uppercase;color:var(--muted);letter-spacing:.5px}
.coef-wrap .value{font-size:34px;font-weight:700;line-height:1.1}
.coef-wrap .value.safe{color:var(--safe)}
.coef-wrap .value.watch{color:var(--watch)}
.coef-wrap .value.hot{color:var(--hot)}
.coef-wrap .value.danger{color:var(--danger)}
.metrics{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:14px}
.metrics .item{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:12px;text-align:center}
.metrics .item .l{font-size:10px;text-transform:uppercase;color:var(--muted);letter-spacing:.5px}
.metrics .item .v{font-size:16px;font-weight:600;margin-top:2px}
.metrics .item .v.green{color:var(--safe)}
.metrics .item .v.yellow{color:var(--watch)}
.metrics .item .v.red{color:var(--danger)}
.chart-wrap{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:6px;margin-bottom:14px}
.chart-wrap .title{font-size:12px;font-weight:600;color:var(--sec);padding:6px 10px 0}
#chart{height:480px}
.bt-section{margin-bottom:14px}
.bt-section h3{font-size:13px;font-weight:600;margin-bottom:8px;color:var(--sec)}
.bt-summary{font-size:11px;color:var(--muted);margin-bottom:8px}
#bt-chart{height:180px;background:var(--card);border:1px solid var(--border);border-radius:10px;padding:4px}
.footer{border-top:1px solid var(--border);padding:12px 0;display:flex;justify-content:space-between;font-size:10px;color:var(--muted)}
.footer a{color:var(--sec);text-decoration:none}
.footer a:hover{color:var(--accent)}
@media(max-width:768px){
  .signal-row{grid-template-columns:1fr}
  .metrics{grid-template-columns:repeat(3,1fr)}
  #chart{height:340px}#bt-chart{height:140px}
  .header{flex-direction:column;align-items:flex-start;gap:6px}
}
</style>
</head>
<body>
<div class="container">

<header class="header">
  <div><h1>SCCO <span>· 相关性系数</span></h1></div>
  <div class="header-meta">%(updated)s<br>共 %(total_days)d 个交易日</div>
</header>

<div class="signal-row">
  <div class="card %(sig_key)s">
    <span class="tag %(sig_key)s">%(sig_tag)s</span>
    <div class="signal-label">相关性系数处于 <strong>%(sig_tag)s</strong> 区间</div>
  </div>
  <div class="card" style="cursor:default">
    <div class="coef-wrap">
      <div class="label">相关性系数</div>
      <div class="value %(sig_key)s">%(ratio).4f</div>
    </div>
  </div>
</div>

<div class="metrics">
  <div class="item"><div class="l">铜期货</div><div class="v">$%(copper).4f</div></div>
  <div class="item"><div class="l">SCCO</div><div class="v">$%(scco_close).2f</div></div>
  <div class="item"><div class="l">安全上沿</div><div class="v green">$%(p_safe).2f</div></div>
  <div class="item"><div class="l">关注上沿</div><div class="v yellow">$%(p_watch).2f</div></div>
  <div class="item"><div class="l">偏热上沿</div><div class="v red">$%(p_hot).2f</div></div>
</div>

<div class="chart-wrap">
  <div class="title">价格走势 · 日线 + 日内 15min</div>
  <div id="chart"></div>
</div>

<div class="bt-section">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <h3>系数区间历史</h3>
    <span class="bt-summary">%(transitions)s 次区间切换 · %(zones_count)s 个交易日</span>
  </div>
  <div id="bt-chart"></div>
</div>

<footer class="footer">
  <div>Data: Yahoo Finance · 每交易日更新</div>
  <div><a href="%(github_url)s">GitHub</a> · <a href="%(pages_url)s">Pages</a></div>
</footer>

</div>

<script>
(function(){var c=%(chart_json)s;if(!c||!c.data||!c.data[0]||!c.data[0].x.length){
  document.getElementById('chart').innerHTML='<div style="text-align:center;padding:80px 20px;color:var(--muted)"><p>暂无数据</p></div>';return}
  Plotly.react('chart',c.data,c.layout,c.config)})();

(function(){var c=%(bt_chart_json)s;if(!c||c==='null'){
  document.getElementById('bt-chart').innerHTML='<div style="text-align:center;padding:40px 20px;color:var(--muted)"><p>数据不足</p></div>';return}
  Plotly.react('bt-chart',c.data,c.layout,c.config)})();

window.addEventListener('resize',function(){
  ['chart','bt-chart'].forEach(function(id){
    var el=document.getElementById(id);if(el&&el.layout)Plotly.Plots.resize(el)})});
</script>
</body>
</html>"""
