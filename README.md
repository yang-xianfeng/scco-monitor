# SCCO Monitor · 相关性系数

监控 SCCO（南方铜业，NYSE:SCCO）市值与铜价锚定市值之间的比率，
衡量估值偏离度。

> **纯系数参考** — 无持仓、无成本、无交易建议。

---

## 目录

- [核心公式](#核心公式)
- [信号区间](#信号区间)
- [架构与数据流](#架构与数据流)
- [输出文件](#输出文件)
- [本地运行](#本地运行)
- [GitHub Actions 部署](#github-actions-部署)
- [环境变量](#环境变量)
- [非交易日兜底](#非交易日兜底)
- [时区说明](#时区说明)
- [设计原则](#设计原则)
- [项目结构](#项目结构)
- [For AI Agents](#for-ai-agents)

---

## 核心公式

```
相关性系数 = SCCO 实际市值 / 铜价锚定市值

铜价锚定市值 = (当前铜价 / 4.2) × 900 × 1e8
SCCO 实际市值 = SCCO 股价 × 流通股数（~7.73亿股）
```

- 系数 **> 1** → SCCO 估值高于铜价锚定
- 系数 **< 1** → SCCO 估值低于铜价锚定
- 阈值可通过环境变量调节，默认 1.08 / 1.18 / 1.28

---

## 信号区间

| 信号 | 系数范围 | 含义 |
|------|----------|------|
| 🟢 安全 | ≤ `THRESHOLD_SAFE` (1.08) | 相对铜价低估 |
| 🟡 关注 | ~ `THRESHOLD_WATCH` (1.18) | 合理区间 |
| 🟠 偏热 | ~ `THRESHOLD_HOT` (1.28) | 估值偏高 |
| 🔴 过热 | ≥ `THRESHOLD_HOT` (1.28) | 显著高估 |

---

## 架构与数据流

```
┌─────────────────────────────────────────────────────┐
│                    main.py                           │
│             入口 · 编排全流程                          │
└─────────┬───────────┬───────────┬───────────────────┘
          │           │           │
          ▼           ▼           ▼
┌──────────────┐ ┌──────────┐ ┌──────────────┐
│ fetcher.py   │ │ core.py  │ │ storage.py   │
│ yfinance     │ │ 计算系数  │ │ CSV 读写      │
│ HG=F / SCCO  │ │ 信号判定  │ │ upsert/append │
└──────┬───────┘ └──────────┘ └──────┬───────┘
       │                             │
       ▼                             ▼
┌──────────────┐           ┌──────────────┐
│ chart.py     │           │ data/        │
│ Plotly JSON  │           │ history.csv  │
│ template.html│           │ intraday.csv │
└──────┬───────┘           └──────────────┘
       │
       ▼
┌──────────────┐
│ docs/        │
│ index.html   │──→ GitHub Pages
│ (Git 推送)   │
└──────────────┘

可选: notifier.py → 飞书 / Telegram
```

### 数据来源

- **yfinance** — Yahoo Finance 免费行情
- **铜期货**: `HG=F`（COMEX 铜期货）
- **股票**: `SCCO`（南方铜业）

### 执行流程

1. **回填历史**（首次 / 数据不足时）→ `fetch_daily_data()` → CSV upsert
2. **拉取当日行情** → `fetch_market_data()` → `MarketData`（非交易日返回 `None`）
3. **拉取日内 K 线** → `fetch_intraday_data()` → `list[IntradayBar]`（仅当日）
4. **计算系数** → `calculate_ratio()` → ratio + 阈值参考价
5. **持久化** → CSV upsert（日线）
6. **生成 HTML** → Plotly candlestick + 历史走势 + 双时区 header
7. **推送通知** → 飞书 / Telegram（可选）

---

## 输出文件

| 文件 | 说明 | 更新策略 |
|------|------|---------|
| `data/history.csv` | 日线 OHLCV + 相关性系数 + 阈值参考价 | 按日 upsert（同一天覆盖） |
| `data/intraday.csv` | 日内 15min K 线 + 系数 | 追加（只增不删） |
| `docs/index.html` | Plotly 监控面板（GitHub Pages） | 每次运行重新生成 |

---

## 本地运行

```bash
pip install -r requirements.txt
python main.py
```

查看 `data/history.csv`（数据）和 `docs/index.html`（图表）。

```bash
python -m pytest tests/ -v    # 34 个测试
```

---

## GitHub Actions 部署

### 前置条件

1. Fork 本仓库
2. GitHub Pages 设置 → Source: **GitHub Actions**
3. 无需数据库、无需服务器

### 触发方式

- **自动**: 美股交易日（Mon-Fri 9:30-16:00 ET）按以下节奏调度

  | 阶段 | 频率 | 覆盖时段 (ET) | cron (UTC) |
  |------|------|---------------|------------|
  | 开盘密集 | 每 5 分钟 | 09:30-09:55 | `30-55/5 13` |
  | 上午盘 | 每 5 分钟 | 10:00-11:55 | `*/5 14-15` |
  | 盘中 | 每 15 分钟 | 12:00-14:55 | `*/15 16-18` |
  | 收盘密集 | 每 5 分钟 | 15:00-16:55 | `*/5 19-20` |

- **手动**: Actions → SCCO Monitor → Run workflow

### 失败重试

`python main.py` 失败后自动重试最多 3 次（bash 循环），3 次均失败才记作 workflow failure。

### 自动提交

成功运行后，`data/` 和 `docs/` 通过 `git-auto-commit-action` 自动推送回仓库（commit message 带 `[skip ci]` 避免循环触发）。

### 清理

每次运行后自动清理旧 workflow runs，保留最近 **5 条**。

### 失败通知

默认 workflow 失败会发邮件到 GitHub 绑定邮箱。
关闭路径：**GitHub Settings → Notifications → Actions** 取消勾选。

---

## 环境变量

| 变量 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `THRESHOLD_SAFE` | float | 1.08 | 安全区间上限 |
| `THRESHOLD_WATCH` | float | 1.18 | 关注区间上限 |
| `THRESHOLD_HOT` | float | 1.28 | 偏热区间上限 |
| `ANCHOR_COPPER_BASE` | float | 4.2 | 锚定铜价基准（公式分母） |
| `ANCHOR_MCAP_FACTOR` | float | 900 | 锚定市值因子 |
| `FEISHU_WEBHOOK` | secret | — | 飞书机器人 Webhook URL |
| `TELEGRAM_BOT_TOKEN` | secret | — | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | secret | — | Telegram 聊天 ID |

> Variables 在 **GitHub Settings → Variables and Secrets → Actions** 中配置。
> Secrets 在同页面的 Secrets 标签页配置。

---

## 非交易日兜底

系统在非交易日（周末/节假日）自动降级运行：

1. `fetch_market_data()` 返回 `None`（yfinance 无数据）
2. `main.py` 使用 CSV 中最后一条已知行情，**不写入新行**
3. HTML 照常生成（展示最后交易日数据）
4. 通知标记 `[Offline]`
5. 首次运行且非交易日时直接退出（无历史数据可展示）

---

## 时区说明

### 调度时区

GitHub Actions cron **永远运行在 UTC**，与账号地区设置无关。
项目通过 UTC→ET 换算确保在美股交易时段触发。

### 显示时区

HTML 页面右上角 Header 同时显示 **美东时间 (ET)** 和 **北京时间**。
15 分钟 K 线图左上角 badge 显示数据最后的 **美东时间**。

### ET ↔ UTC ↔ 北京时间换算

| 概念 | 值 |
|------|-----|
| EDT（夏令时，约 3 月-11 月） | UTC-4 |
| EST（冬令时，约 11 月-3 月） | UTC-5 |
| 北京时间（全年） | UTC+8 |

**例：当前为 7 月（EDT）**

```
09:30 EDT（开盘）= 13:30 UTC = 21:30 北京时间
16:00 EDT（收盘）= 20:00 UTC = 04:00 北京时间（次日）
```

---

## 设计原则

- **纯系数参考** — 无持仓、无成本、无交易建议
- **可配置阈值** — 所有阈值从环境变量读取，空值自动回退默认值
- **零冗余依赖** — 仅 yfinance / requests / pandas
- **CSV 即数据仓库** — 零运维成本，无需数据库
- **非交易日兜底** — 周末/节假日自动使用最后已知数据
- **双时区显示** — 方便跨时区查看

---

## 项目结构

```
main.py                 # 入口 · 编排流程
scco_monitor/
├── __init__.py         # 包版本信息
├── config.py           # 全局配置（阈值 / 时区 / 路径 / 环境变量）
├── models.py           # TypedDict 数据模型 + Signal 枚举
├── fetcher.py          # yfinance 数据采集（日线 + 15min 日内）
├── core.py             # 相关性系数计算 + 信号判定
├── storage.py          # CSV 读写（日线 upsert + 日内 append）
├── zone.py             # 系数区间转换历史扫描
├── notifier.py         # 飞书 / Telegram 推送
├── chart.py            # Plotly 图表 + HTML 渲染
└── template.html       # HTML 模板
data/                   # CSV 数据存储
docs/                   # GitHub Pages 静态页面
tests/                  # 测试用例
.github/workflows/      # GitHub Actions 工作流
```

---

## For AI Agents

如果你是 AI 助手，请先阅读 `AGENTS.md` 获取完整的项目知识和操作指南。
