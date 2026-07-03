# SCCO Monitor · Cola 铜价系数模型

监控 SCCO（南方铜业）相对铜价的杠杆率系数，自动生成 K 线图表与交易信号。

## 快速开始

```bash
pip install -r requirements.txt
python main.py
```

首次运行后查看 `data/history.csv` 和 `docs/index.html`。

## 原理

Cola 铜价系数 = 实际市值 / 锚定市值

| 系数区间 | 信号 | 操作建议 |
|----------|------|----------|
| ≤ 1.10 | 🟢 安全 | 逢低分批买入 |
| 1.10 ~ 1.20 | 🟡 合理 | 持有观望 |
| 1.20 ~ 1.50 | 🟠 偏热 | 停止加仓 |
| ≥ 1.50 | 🔴 减仓 | 分批减仓 |

锚定市值反映"当前铜价下 SCCO 应有的合理市值"，实际市值是市场给的估值，两者比值衡量偏离度。

## 输出

| 文件 | 说明 |
|------|------|
| `data/history.csv` | 每日 OHLCV + 系数 + 参考价，可直接用于回测 |
| `docs/index.html` | Plotly K 线图 + P₁.₁₀/P₁.₂₀/P₁.₅₀ 参考线，GitHub Pages 查看 |

## GitHub Actions

每个交易日运行两次（开盘后 ≈UTC 14:00 / 收盘后 ≈UTC 20:30），自动：
1. 采集数据、计算系数
2. 更新 `data/history.csv`（同日期覆盖，不重复）
3. 生成 `docs/index.html`
4. 可选推送飞书/Telegram
5. 自动提交回仓库

### 配置

| 变量 | 类型 | 说明 |
|------|------|------|
| `USER_COST` | Variables | 持仓成本价，用于计算浮亏 |
| `FEISHU_WEBHOOK` | Secrets | 飞书机器人 Webhook |
| `TELEGRAM_BOT_TOKEN` | Secrets | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | Secrets | Telegram Chat ID |

通知渠道均为可选，不配则静默运行。

### GitHub Pages 启用

1. 仓库 Settings → Pages
2. Source: **Deploy from a branch**
3. Branch: `main`, folder: `/docs`
4. Save → 等待几分钟，`https://<user>.github.io/scco-monitor/` 即可访问图表

## 测试

```bash
pip install pytest pytest-mock
python -m pytest tests/ -v
```

## 参考设计文档

原始需求文档 [`项目开发初始需求文档（需进一步更改）.md`](项目开发初始需求文档（需进一步更改）.md) 保留了完整策略背景与远期扩展思路。

## 设计原则

- **单文件优先** — 整个逻辑封装在 `main.py`，无包/框架/数据库
- **CSV 即数据仓库** — 不引入数据库，CSV 可直接导入回测
- **无技术分析指标** — Cola 系数本身就是策略，MACD/RSI 等不增加价值
- **通知非必需** — 不配置 Webhook 则只更新图表，零干扰
