"""Tests for SCCO Monitor — Cola 铜价系数模型."""

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

import main

# ── Fixtures ──────────────────────────────────────

@pytest.fixture
def sample_data():
    return {
        "date": "2026-07-03",
        "copper": 6.2290,
        "scco_open": 171.00,
        "scco_high": 175.89,
        "scco_low": 169.14,
        "scco_close": 172.01,
        "scco_volume": 1_454_500,
        "shares": 773_000_000,
    }

@pytest.fixture
def sample_cola():
    return {
        "ratio": 1.0752,
        "p_110": 175.98,
        "p_120": 191.98,
        "p_150": 239.97,
    }

@pytest.fixture
def tmp_workspace(tmp_path):
    """Patch main globals to use temp dirs."""
    data_dir = tmp_path / "data"
    docs_dir = tmp_path / "docs"
    data_dir.mkdir()
    docs_dir.mkdir()
    with patch.object(main, "DATA_DIR", data_dir):
        with patch.object(main, "DOCS_DIR", docs_dir):
            with patch.object(main, "CSV_PATH", data_dir / "history.csv"):
                with patch.object(main, "HTML_PATH", docs_dir / "index.html"):
                    yield tmp_path


# ── calculate_cola ────────────────────────────────

class TestCalculateCola:
    def test_basic(self, sample_data):
        result = main.calculate_cola(sample_data)
        assert isinstance(result, dict)
        assert "ratio" in result
        assert 0 < result["ratio"] < 5
        assert result["p_110"] < result["p_120"] < result["p_150"]

    def test_safe_zone(self):
        r = main.calculate_cola({"copper": 6.00, "scco_close": 100, "shares": 773_000_000})
        assert r["ratio"] < 0.8

    def test_danger_zone(self):
        r = main.calculate_cola({"copper": 4.00, "scco_close": 300, "shares": 773_000_000})
        assert r["ratio"] > 1.50

    def _anchor_to_price(self, anchor, ratio, shares):
        return ratio * anchor / shares

    def test_boundary_consistency(self):
        data = {"copper": 6.229, "scco_close": 172.01, "shares": 773_000_000}
        r = main.calculate_cola(data)
        anchor = data["copper"] / 4.2 * 900 * 1e8
        for mult, key in [(1.10, "p_110"), (1.20, "p_120"), (1.50, "p_150")]:
            expected = mult * anchor / data["shares"]
            assert abs(r[key] - expected) < 0.01

    def test_near_zero_copper(self):
        r = main.calculate_cola({"copper": 0.01, "scco_close": 100, "shares": 773_000_000})
        assert r["ratio"] > 100  # anchor cap ~0 → ratio blows up
        assert r["p_110"] < r["p_120"] < r["p_150"]

    def test_large_shares(self):
        r = main.calculate_cola({"copper": 6.00, "scco_close": 50, "shares": 10_000_000_000})
        assert 0 < r["ratio"] < 10

    def test_ratio_one_means_fair_value(self):
        """When ratio=1, SCCO price should equal anchor / shares."""
        copper = 6.00
        shares = 773_000_000
        anchor = copper / 4.2 * 900 * 1e8
        fair_price = anchor / shares
        r = main.calculate_cola({"copper": copper, "scco_close": fair_price, "shares": shares})
        assert abs(r["ratio"] - 1.0) < 0.001

# ── get_signal ────────────────────────────────────

class TestGetSignal:
    @pytest.mark.parametrize("ratio,expected", [
        (0.50, "safe"), (1.00, "safe"), (1.10, "safe"),
        (1.100001, "watch"), (1.15, "watch"), (1.20, "watch"),
        (1.200001, "hot"), (1.30, "hot"), (1.499999, "hot"),
        (1.50, "danger"), (2.00, "danger"),
    ])
    def test_boundaries(self, ratio, expected):
        name, *_ = main.get_signal(ratio)
        assert name == expected, f"ratio={ratio} → {name}, expected {expected}"

    def test_returns_four_values(self):
        assert len(main.get_signal(1.0)) == 4
        assert all(isinstance(v, str) for v in main.get_signal(1.0))

# ── CSV ───────────────────────────────────────────

class TestCSV:
    def _write_one(self, date="2026-01-01", close=100, ratio=0.9):
        main.append_csv(
            {"date": date, "copper": 5.0, "scco_open": 100, "scco_high": 101,
             "scco_low": 99, "scco_close": close, "scco_volume": 1000},
            {"ratio": ratio, "p_110": 100, "p_120": 110, "p_150": 130},
        )

    def test_creates_file(self, tmp_workspace):
        self._write_one()
        assert main.CSV_PATH.exists()

    def test_roundtrip(self, tmp_workspace):
        self._write_one("2026-01-01")
        self._write_one("2026-01-02", close=102, ratio=0.95)
        rows = main.read_csv()
        assert len(rows) == 2
        assert rows[0]["date"] == "2026-01-01"
        assert rows[1]["date"] == "2026-01-02"

    def test_upsert_same_date(self, tmp_workspace):
        self._write_one("2026-01-01", close=100)
        self._write_one("2026-01-01", close=105)
        rows = main.read_csv()
        assert len(rows) == 1
        assert rows[0]["scco_close"] == "105"

    def test_all_fields_present(self, tmp_workspace):
        self._write_one()
        rows = main.read_csv()
        for f in main.FIELDS:
            assert f in rows[0], f"missing field: {f}"

    def test_empty_csv_returns_empty(self, tmp_workspace):
        assert main.read_csv() == []

    def test_sort_by_date(self, tmp_workspace):
        self._write_one("2026-01-03")
        self._write_one("2026-01-01")
        self._write_one("2026-01-02")
        rows = main.read_csv()
        dates = [r["date"] for r in rows]
        assert dates == ["2026-01-01", "2026-01-02", "2026-01-03"]

# ── HTML ──────────────────────────────────────────

class TestBuildHTML:
    def test_empty_state(self, tmp_workspace, sample_data, sample_cola):
        main.build_html([], sample_data, sample_cola)
        html = main.HTML_PATH.read_text(encoding="utf-8")
        assert "暂无数据" in html

    def test_with_rows(self, tmp_workspace, sample_data, sample_cola):
        row = {**sample_data, **sample_cola}
        main.build_html([row], sample_data, sample_cola)
        html = main.HTML_PATH.read_text(encoding="utf-8")
        assert "Plotly.newPlot" in html
        assert "172.01" in html
        assert "当前系数" in html

    def test_embeds_data_json(self, tmp_workspace, sample_data, sample_cola):
        row = {**sample_data, **sample_cola}
        main.build_html([row], sample_data, sample_cola)
        html = main.HTML_PATH.read_text(encoding="utf-8")
        assert "172.01" in html

    def test_status_bar_not_shown_when_empty(self, tmp_workspace, sample_data, sample_cola):
        main.build_html([], sample_data, sample_cola)
        html = main.HTML_PATH.read_text(encoding="utf-8")
        assert "当前系数" not in html

    def test_status_bar_shown_with_data(self, tmp_workspace, sample_data, sample_cola):
        row = {**sample_data, **sample_cola}
        main.build_html([row], sample_data, sample_cola)
        html = main.HTML_PATH.read_text(encoding="utf-8")
        assert "当前系数" in html

# ── fetch_market_data ─────────────────────────────

class TestFetchMarketData:
    @patch("main.yf.Ticker")
    def test_success(self, mock_ticker):
        mock_copper, mock_scco = MagicMock(), MagicMock()
        mock_ticker.side_effect = lambda t: mock_copper if t == "HG=F" else mock_scco

        mock_copper.history.return_value = pd.DataFrame({"Close": [6.229]})
        mock_scco.history.return_value = pd.DataFrame({
            "Open": [171.0], "High": [175.89], "Low": [169.14],
            "Close": [172.01], "Volume": [1_454_500],
        })
        mock_scco.info = {"sharesOutstanding": 773_000_000}

        result = main.fetch_market_data()
        assert result["copper"] == 6.229
        assert result["scco_close"] == 172.01
        assert result["shares"] == 773_000_000

    @patch("main.yf.Ticker")
    def test_empty_history_exits(self, mock_ticker):
        mock_ticker.return_value.history.return_value = pd.DataFrame()
        with pytest.raises(SystemExit):
            main.fetch_market_data()

    @patch("main.yf.Ticker")
    def test_fallback_shares(self, mock_ticker):
        mock_copper, mock_scco = MagicMock(), MagicMock()
        mock_ticker.side_effect = lambda t: mock_copper if t == "HG=F" else mock_scco

        mock_copper.history.return_value = pd.DataFrame({"Close": [6.0]})
        mock_scco.history.return_value = pd.DataFrame({
            "Open": [100], "High": [101], "Low": [99],
            "Close": [100], "Volume": [1000],
        })
        mock_scco.info = {}

        result = main.fetch_market_data()
        assert result["shares"] == 773_000_000

    @patch("main.yf.Ticker")
    def test_none_shares_defaults(self, mock_ticker):
        mock_copper, mock_scco = MagicMock(), MagicMock()
        mock_ticker.side_effect = lambda t: mock_copper if t == "HG=F" else mock_scco

        mock_copper.history.return_value = pd.DataFrame({"Close": [6.0]})
        mock_scco.history.return_value = pd.DataFrame({
            "Open": [100], "High": [101], "Low": [99],
            "Close": [100], "Volume": [1000],
        })
        mock_scco.info = {"sharesOutstanding": None}

        result = main.fetch_market_data()
        assert result["shares"] == 773_000_000

# ── push_notification ─────────────────────────────

class TestPushNotification:
    @patch("main.requests.post")
    def test_both_empty_quiet(self, mock_post):
        main.push_notification("x")
        mock_post.assert_not_called()

    @patch("main.requests.post")
    def test_feishu_only(self, mock_post):
        with patch.object(main, "FEISHU_WEBHOOK", "https://feishu.test/hook"):
            main.push_notification("hello")
        mock_post.assert_called_once()

    @patch("main.requests.post")
    def test_telegram_only(self, mock_post):
        with patch.object(main, "TELEGRAM_BOT_TOKEN", "bot:123"):
            with patch.object(main, "TELEGRAM_CHAT_ID", "456"):
                main.push_notification("hello")
        mock_post.assert_called_once()

    @patch("main.requests.post")
    def test_both_channels(self, mock_post):
        with patch.object(main, "FEISHU_WEBHOOK", "https://feishu.test/hook"):
            with patch.object(main, "TELEGRAM_BOT_TOKEN", "bot:123"):
                with patch.object(main, "TELEGRAM_CHAT_ID", "456"):
                    main.push_notification("hello")
        assert mock_post.call_count == 2

    @patch("main.requests.post", side_effect=Exception("timeout"))
    def test_failure_does_not_raise(self, mock_post):
        with patch.object(main, "FEISHU_WEBHOOK", "https://feishu.test/hook"):
            main.push_notification("hello")
