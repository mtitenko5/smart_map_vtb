from datetime import datetime, timedelta

import pandas as pd

from logic import (
    _parse_bool,
    compute_period_delta,
    get_filtered_data,
    get_monthly_average_spend,
    get_offer_goal_status,
    get_offer_performance,
    get_offer_status,
    summarize_metrics,
)


def test_parse_bool_handles_common_values():
    assert _parse_bool(True) is True
    assert _parse_bool(False) is False
    assert _parse_bool("true") is True
    assert _parse_bool("1") is True
    assert _parse_bool("yes") is True
    assert _parse_bool("false") is False
    assert _parse_bool("0") is False
    assert _parse_bool(None) is False


def test_get_offer_status_for_expired_today_and_soon():
    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
    today = datetime.now().date().isoformat()
    soon = (datetime.now().date() + timedelta(days=2)).isoformat()

    status_expired, text_expired = get_offer_status(yesterday)
    status_today, text_today = get_offer_status(today)
    status_soon, text_soon = get_offer_status(soon)

    assert status_expired == "expired"
    assert "Истёк" in text_expired

    assert status_today == "active"
    assert text_today == "Истекает сегодня"

    assert status_soon == "soon"
    assert "Осталось 2 дн." == text_soon


def test_get_filtered_data_filters_by_category_and_date_range():
    df = pd.DataFrame(
        {
            "date": ["2026-04-01", "2026-04-05", "2026-04-10"],
            "category": ["кафе", "аптеки", "кафе"],
            "amount": [500, 700, 300],
        }
    )

    result = get_filtered_data(
        df=df,
        category="кафе",
        start_date="2026-04-01",
        end_date="2026-04-07",
    )

    assert len(result) == 1
    assert result.iloc[0]["category"] == "кафе"
    assert result.iloc[0]["amount"] == 500


def test_get_monthly_average_spend_returns_mean_per_month():
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2026-03-01", "2026-03-15", "2026-04-05", "2026-04-20"]
            ),
            "category": ["кафе", "кафе", "кафе", "супермаркеты"],
            "amount": [1000, 500, 900, 2000],
        }
    )

    # March total = 1500, April total for "кафе" = 900, mean = 1200
    assert get_monthly_average_spend(df, "кафе") == 1200.0
    assert get_monthly_average_spend(df, "аптеки") == 0.0


def test_get_offer_performance_returns_expected_keys_and_positive_values():
    offer = {
        "id": 1,
        "discount_percent": 15,
        "min_purchase_amount": 500,
    }

    perf = get_offer_performance(offer)

    assert set(perf.keys()) == {
        "views",
        "redemptions",
        "new_clients",
        "revenue",
        "conversion",
        "roi",
        "avg_check",
    }
    assert perf["views"] > 0
    assert perf["redemptions"] >= 0
    assert perf["new_clients"] >= 0
    assert perf["revenue"] > 0
    assert perf["conversion"] >= 0


def test_get_offer_goal_status_handles_progress_and_achievement():
    offer = {
        "goal_enabled": True,
        "goal_metric": "new_clients",
        "goal_target": 20,
    }
    performance = {
        "new_clients": 25,
    }

    goal = get_offer_goal_status(offer, performance)

    assert goal["enabled"] is True
    assert goal["metric"] == "new_clients"
    assert goal["achieved"] is True
    assert goal["progress"] == 100
    assert goal["remaining"] == 0


def test_compute_period_delta_handles_zero_previous_value():
    label, raw = compute_period_delta(10, 0)
    assert label == "Новый показатель"
    assert raw == "+100%"

    label_zero, raw_zero = compute_period_delta(0, 0)
    assert label_zero == "0% к прошлому периоду"
    assert raw_zero == "0%"


def test_summarize_metrics_aggregates_dataframe_correctly():
    df = pd.DataFrame(
        {
            "new_clients": [5, 7],
            "revenue": [1000.0, 2000.0],
            "total_transactions": [10, 20],
            "average_check": [100.0, 120.0],
            "repeat_clients": [3, 4],
        }
    )

    summary = summarize_metrics(df)

    assert summary["new_clients"] == 12
    assert summary["revenue"] == 3000.0
    assert summary["transactions"] == 30
    assert summary["avg_check"] == 110.0
    assert summary["repeat_clients"] == 7