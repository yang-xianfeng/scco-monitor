# GitHub Actions 工作原理

> 本文以本项目的 `run.yml` 为蓝本，从零讲解 GitHub Actions 的运作机制，
> 帮助你系统理解这个监控面板是如何自动跑起来的。

---

## 一、什么是 GitHub Actions？

GitHub Actions 是 GitHub 内置的**自动化流水线**服务。你可以把它理解为：
你在 GitHub 仓库里放了一个"脚本"，GitHub 会按你设定的**触发条件**自动执行它。

在 SCCO Monitor 这个项目里，它做三件事：

1. **拉取数据** — 从 Yahoo Finance 获取铜价和 SCCO 股价
2. **计算系数** — 算相关性系数，生成图表
3. **发布网页** — 把 HTML 部署到 GitHub Pages，同时把数据提交回仓库

整个过程**不需要**你有一台 24 小时运行的电脑或服务器。

---

## 二、触发器（什么时候跑？）

配置文件在 `.github/workflows/run.yml`，开头就是触发器定义：

### 2.1 schedule — 定时自动运行

```yaml
on:
  schedule:
    - cron: '30-55/5 13 * * 1-5'
    - cron: '*/5 14-15 * * 1-5'
    - cron: '*/15 16-18 * * 1-5'
    - cron: '*/5 19-20 * * 1-5'
```

**cron 语法：**

```
┌───────── 分钟 (0-59)
│ ┌───────── 小时 (0-23)
│ │ ┌───────── 日 (1-31)
│ │ │ ┌───────── 月 (1-12)
│ │ │ │ ┌───────── 星期 (0-6, 0=周日)
│ │ │ │ │
*/5 14 * * 1-5
```

- `*/5` = 每 5 分钟
- `30-55/5` = 从第 30 到第 55 分钟，每 5 分钟
- `*` = 任意（每天都跑、每月都跑）
- `1-5` = 周一至周五

组合起来，这 4 条 cron 在 **周一至周五** 覆盖了 **UTC 13:30 ~ 20:55**。

### 2.2 workflow_dispatch — 手动触发

```yaml
on:
  workflow_dispatch:
```

在 GitHub 网页上打开 **Actions → SCCO Monitor → "Run workflow"** 按钮，可以随时手动运行一次。

### 2.3 push — 代码更新时触发

```yaml
on:
  push:
    branches: [main]
    paths-ignore:
      - 'data/**'
      - 'docs/**'
```

当你推送代码到 main 分支时也会自动运行，但排除 `data/` 和 `docs/` 目录的变更（避免 auto-commit 导致无限循环）。

---

## 三、时区（最重要的概念）

### 核心结论

**GitHub Actions 的 cron 永远运行在 UTC！**

这与你的 GitHub 账号地区设置、电脑系统时间**完全无关**。
UTC 是国际标准时间（≈ 伦敦时间），不受夏令时影响。

### 换算到美东时间 (ET)

美国有夏令时/冬令时，所以 UTC → ET 的换算分两种：

| 季节 | 美东简称 | 与 UTC 的关系 | 适用月份 |
|------|---------|--------------|---------|
| 夏令时 | EDT | UTC - 4 小时 | 约 3 月中 ~ 11 月初 |
| 冬令时 | EST | UTC - 5 小时 | 约 11 月初 ~ 3 月中 |

### 美股交易时间

美股交易时段是 **周一至周五 09:30 - 16:00 ET**。

### 换算表（以当前 7 月 EDT 为例）

```
cron 写的是 UTC，GitHub 按 UTC 执行。
要让它在 09:30-16:00 ET 内触发，就需要把 ET 时间换算成 UTC。

09:30 ET = 09:30 + 4 = 13:30 UTC  ［夏令时］
16:00 ET = 16:00 + 4 = 20:00 UTC  ［夏令时］
```

项目里的 4 条 cron 覆盖了 UTC 13:30-20:55：

| cron (UTC) | EDT (7 月，夏令) | EST (1 月，冬令) | 覆盖的时段 |
|-----------|-----------------|-----------------|----------|
| `30-55/5 13` | 09:30-09:55 开盘 | 08:30-08:55 盘前 | 开盘首 25 分钟 |
| `*/5 14-15` | 10:00-11:55 | 09:00-10:55 盘前~早盘 | 开盘第 1-2 小时 |
| `*/15 16-18` | 12:00-14:55 | 11:00-13:55 | 盘中 |
| `*/5 19-20` | 15:00-16:55 | 14:00-15:55 | 收盘前后 |

**注意冬令时的问题：** EST 时，前两条 cron 在 08:30-10:55 触发，比美股开盘 (09:30) 早或刚好覆盖早盘。这**不会报错** —— 因为 `main.py` 中 `fetch_market_data()` 拉不到数据时会返回 `None`，自动降级使用最后已知数据。

### 换算到北京时间

北京时间 = UTC + 8 小时（全年不变）。

| cron (UTC) | EDT（夏令）→ 北京时间 | EST（冬令）→ 北京时间 |
|-----------|---------------------|---------------------|
| 13:30 | 21:30 | 21:30 |
| 14:00 | 22:00 | 22:00 |
| 16:00 | 00:00 (次日) | 00:00 (次日) |
| 19:00 | 03:00 (次日) | 03:00 (次日) |
| 20:55 | 04:55 (次日) | 04:55 (次日) |

你会发现：**北京时间表示下，UTC 不同时段的换算结果是一样的**（因为 UTC 到北京时间固定 +8）。区别只在 ET 一侧 —— 同一 UTC 时刻，EDT 和 EST 读出来差 1 小时。

---

## 四、权限（GitHub 允许它做什么？）

```yaml
permissions:
  contents: write    # 可以提交代码（用于 auto-commit 数据）
  pages: write       # 可以部署 GitHub Pages
  id-token: write    # 用于 Pages 部署的身份验证
  actions: write     # 可以删除 workflow runs（用于清理旧记录）
```

这些权限通过 `${{ github.token }}` 自动授权，不需要你手动配置任何密钥。

---

## 五、Job 和 Steps（具体做什么？）

每次触发后，执行一个叫 `deploy` 的 **job**（任务），它包含一系列 **steps**（步骤）：

### 步骤全景图

```
┌─────────────────────────────────────┐
│ ① Checkout（拉取代码）                │
├─────────────────────────────────────┤
│ ② Setup Python（安装 Python 3.12）   │
├─────────────────────────────────────┤
│ ③ pip install（安装依赖）             │
├─────────────────────────────────────┤
│ ④ Run monitor（运行主程序，失败重试 3 次）│
├─────────────────────────────────────┤
│ ⑤ Setup Pages（配置 GitHub Pages）    │
├─────────────────────────────────────┤
│ ⑥ Upload artifact（上传 HTML）        │
├─────────────────────────────────────┤
│ ⑦ Deploy to Pages（部署网页）          │
├─────────────────────────────────────┤
│ ⑧ Commit data back（数据提交回仓库）    │
├─────────────────────────────────────┤
│ ⑨ Cleanup runs（清理旧记录，保留 5 条） │
└─────────────────────────────────────┘
```

### 各步骤详解

#### ① Checkout

```yaml
- uses: actions/checkout@v4
```

把你的仓库代码下载到 GitHub 的云服务器上，后面所有的操作都在这个代码目录里进行。

#### ② Setup Python

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: '3.12'
    cache: pip
```

安装 Python 3.12，并缓存 pip 依赖（下次运行更快）。

#### ③ pip install

```yaml
- run: pip install -r requirements.txt
```

安装项目依赖：yfinance、pandas、requests、plotly。

#### ④ Run monitor （核心步骤）

```yaml
- name: Run monitor (retry 3x)
  run: |
    for i in {1..3}; do
      python main.py && exit 0
      echo "重试 $i/3 失败，5秒后重试..."
      sleep 5
    done
    echo "3次均失败"
    exit 1
```

这是整个流程的核心。它：

1. 运行 `python main.py`
2. 如果成功 (`&&`) → 立即退出（`exit 0`）
3. 如果失败 → 等 5 秒后重试，最多 3 次
4. 如果 3 次都失败 → `exit 1` 标记整个 job 失败

**为什么需要重试？** 因为 yfinance 偶尔会因为网络波动、API 限流等原因临时失败，重试一两次通常就能恢复。

这一步还注入了环境变量：

```yaml
env:
  THRESHOLD_SAFE: ${{ vars.THRESHOLD_SAFE }}
  THRESHOLD_WATCH: ${{ vars.THRESHOLD_WATCH }}
  THRESHOLD_HOT: ${{ vars.THRESHOLD_HOT }}
  FEISHU_WEBHOOK: ${{ secrets.FEISHU_WEBHOOK }}
```

- `${{ vars.XXX }}` 读取 GitHub 的 **Variables**（明文变量）
- `${{ secrets.XXX }}` 读取 GitHub 的 **Secrets**（加密变量）

#### ⑤ ⑥ ⑦ GitHub Pages 部署

```yaml
- uses: actions/configure-pages@v6
- uses: actions/upload-pages-artifact@v5
  with:
    path: ./docs
- uses: actions/deploy-pages@v5
```

这三步把上一步生成的 `docs/index.html` 部署到 GitHub Pages。

整个过程：
1. 配置 Pages
2. 把 `docs/` 目录打包上传为"构建产物"（artifact）
3. 部署到 Pages 服务器

**成功 → 网页更新；失败 → 网页保持上次成功版本不变。**

#### ⑧ Commit data back

```yaml
- name: Commit data back to repo
  if: success()
  uses: stefanzweifel/git-auto-commit-action@v7
  with:
    commit_message: "auto: update data & chart [skip ci]"
    file_pattern: data/ docs/
```

- 仅在**前面的步骤全部成功**时才执行（`if: success()`）
- 把 `data/`（CSV 数据）和 `docs/`（HTML 页面）自动提交回仓库
- commit message 带 `[skip ci]`，避免 auto-commit 再次触发 workflow

#### ⑨ Cleanup old runs

```yaml
- name: Cleanup old runs (keep last 5)
  if: always()
  uses: Mattraks/delete-workflow-runs@v2
  with:
    token: ${{ github.token }}
    repository: ${{ github.repository }}
    retain_days: 0
    keep_minimum_runs: 5
```

- `if: always()` → **不管前面的步骤成功还是失败**，都会执行
- 删除旧的 workflow runs，只保留最近 5 条
- 避免 Actions 页面堆积太多历史记录

---

## 六、成功 vs 失败的行为对比

### 运行成功时

```
main.py 成功运行
  → HTML 生成
  → 部署到 GitHub Pages → 网页更新
  → 数据 auto-commit 回仓库
  → 清理旧 runs
  → ✓ 绿色勾
```

### 运行失败时（3 次重试都失败）

```
main.py 3 次都失败
  → 跳过 Pages 部署 → 网页保持上一个成功版本
  → 跳过 auto-commit → 仓库数据不变
  → 仍然清理旧 runs
  → ✗ 红色叉（但网页正常显示！）
```

**关键：就算这次失败，你的网页仍然显示着上次成功的数据。**

---

## 七、常见问题

### Q: Actions 页面有很多条运行记录，正常吗？

**正常。** 每条 cron 触发就是一个独立的 run。项目在交易日每 5-15 分钟跑一次，一天会产生约 40 条记录。页面底部的清理步骤会保留最近 5 条。

### Q: 为什么晚上打开网页看到的是旧数据？

因为美股在北京时间晚上 21:30 开盘。如果你在 21:30 之前打开，今天的 cron 还没开始运行，网页显示的是上一个交易日的数据。**这是正常行为，不是 bug。**

### Q: 如果我手动触发 Run workflow，有什么区别？

和 cron 自动触发完全一样——都是执行同一个 `deploy` job。只是触发方式不同。

### Q: GitHub Actions 有免费额度限制吗？

**有，但对本项目足够。** GitHub 免费版每个月有 2000 分钟的 Actions 额度。本项目每次运行约 2 分钟，就算一天跑 40 次，一个月约 2400 分钟，略微超出。但实际运行不会那么密集（非交易日不跑，且每小时也有非覆盖时段）。基本上不用担心额度用超。

### Q: 为什么我打开 Actions 页面看到的是黄灯/进行中？

说明这次运行还没结束。通常 1-3 分钟内会完成。如果长时间卡住（>10 分钟），可能是 GitHub 排队或网络问题，可以手动取消重新触发。

---

## 八、一次运行的完整日志解读

打开任意一条 workflow run，你会看到类似这样的日志：

```
Run monitor (retry 3x)
  ==========================================
    SCCO Monitor · 相关性系数
    2026-07-06 15:30:00
  ==========================================
  [1] 历史数据: 120 日
  [2] 行情: 铜 $6.229  |  SCCO $172.01
  [3] 日内: 8 根 15min K 线
  [4] 系数: 0.9961 (安全)
  [5] CSV: 120 行
  [6] HTML 已生成

  【SCCO Monitor】07-06 15:30 [Offline]
  铜 $6.229  |  SCCO $172.01
  系数 0.9961  |  安全
  📊 https://xxx.github.io/SCCO-Monitor/

  ==========================================
  ✓ 完成
  ==========================================
  ✓ Run monitor 成功
  ✓ Setup Pages 成功
  ✓ Upload artifact 成功
  ✓ Deploy to Pages 成功
  ✓ Commit data back 成功
  ✓ Cleanup old runs 成功
```

如果失败，你会看到重试信息：

```
Run monitor (retry 3x)
  ... (第一次运行的错误日志)
  重试 1/3 失败，5秒后重试...
  ... (第二次运行的错误日志)
  重试 2/3 失败，5秒后重试...
  ... (第三次运行的错误日志)
  3次均失败
  ✗ Run monitor 失败 → Job failed
  后续步骤被跳过（但清理步骤 still 运行）
```

---

## 九、配置总览

```
run.yml（配置文件）
  │
  ├─ on.schedule ─────── 4 条 cron，覆盖美股交易时段
  │
  ├─ permissions ─────── 允许写入代码 + 部署 Pages + 删除旧 runs
  │
  └─ jobs.deploy.steps
       ├─ checkout@v4        ─── 拉取代码
       ├─ setup-python@v5    ─── 安装 Python
       ├─ pip install        ─── 安装依赖
       ├─ Run monitor        ─── bash 重试循环运行 main.py
       ├─ configure-pages@v6 ─── 配置 Pages
       ├─ upload-pages-artifact ── 上传 HTML
       ├─ deploy-pages@v5    ─── 部署网页
       ├─ git-auto-commit    ─── 提交数据回仓库
       └─ delete-workflow-runs ── 清理旧 runs
```

---

## 十、关键词速查

| 关键词 | 说明 |
|--------|------|
| cron | 定时表达式，GitHub 用 UTC 执行 |
| UTC | 协调世界时，cron 的基准时间 |
| ET / EDT / EST | 美东时间 / 夏令时 / 冬令时 |
| workflow | 一个自动化流程（= 一个 .yml 文件） |
| job | 一个工作单元（= 一台云服务器上跑完的系列步骤） |
| step | 一个操作步骤 |
| runner | 执行 job 的云服务器（ubuntu-latest） |
| artifact | 构建产物（上传的 HTML 文件） |
| token | 自动生成的临时密钥，用于 API 调用 |
| vars | 明文变量（在 GitHub Settings 中配置） |
| secrets | 加密变量（在 GitHub Settings 中配置） |
| Pages | GitHub 的静态网页托管服务 |
