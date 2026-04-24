from __future__ import annotations

from datetime import datetime
import math

import pandas as pd


GOAL_METRIC_LABELS = {
    "new_clients": "Новые клиенты",
    "redemptions": "Активации",
    "revenue": "Выручка",
}


def _parse_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes")
    if isinstance(val, (int, float)):
        return bool(val)
    return False


def safe_float(value, default=0.0) -> float:
    try:
        if pd.isna(value):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def safe_int(value, default=0) -> int:
    try:
        if pd.isna(value):
            return int(default)
        return int(float(value))
    except Exception:
        return int(default)


def format_money(value: float) -> str:
    return f"₽{int(round(value)):,}".replace(",", " ")


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    radius = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def estimate_distance_text(lat, lon, ref_lat, ref_lon) -> str:
    try:
        km = haversine_km(float(lat), float(lon), float(ref_lat), float(ref_lon))
    except Exception:
        return "Расстояние уточняется"
    if km < 1:
        return f"{int(round(km * 1000))} м"
    return f"{km:.1f} км"


def get_offer_status(valid_until_str):
    if pd.isna(valid_until_str):
        return "unknown", "Неизвестно"
    try:
        exp_date = pd.to_datetime(valid_until_str).date()
    except Exception:
        return "unknown", "Неизвестно"

    today = datetime.now().date()
    days_left = (exp_date - today).days

    if days_left < 0:
        return "expired", f"Истёк {abs(days_left)} дн. назад"
    if days_left == 0:
        return "active", "Истекает сегодня"
    if days_left <= 3:
        return "soon", f"Осталось {days_left} дн."
    return "active", f"Осталось {days_left} дн."


def get_filtered_data(df: pd.DataFrame, category: str, start_date, end_date) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    filtered = df.copy()
    filtered["date"] = pd.to_datetime(filtered["date"])

    mask = (filtered["date"] >= pd.to_datetime(start_date)) & (
        filtered["date"] <= pd.to_datetime(end_date)
    )

    if category != "Все":
        mask &= filtered["category"] == category

    return filtered[mask].reset_index(drop=True)


def compute_period_delta(current_value, previous_value) -> tuple[str, str]:
    if previous_value == 0:
        if current_value == 0:
            return "0% к прошлому периоду", "0%"
        return "Новый показатель", "+100%"

    delta_pct = ((current_value - previous_value) / previous_value) * 100
    sign = "↑" if delta_pct >= 0 else "↓"
    return f"{sign} {abs(delta_pct):.1f}% к прошлому периоду", f"{delta_pct:+.1f}%"


def get_monthly_average_spend(df: pd.DataFrame, category: str) -> float:
    if df.empty:
        return 0.0

    cat_df = df[df["category"] == category].copy()
    if cat_df.empty:
        return 0.0

    cat_df["date"] = pd.to_datetime(cat_df["date"])
    cat_df["month"] = cat_df["date"].dt.to_period("M")
    per_month = cat_df.groupby("month")["amount"].sum()

    if per_month.empty:
        return 0.0

    return float(per_month.mean())


def get_offer_performance(offer: dict) -> dict:
    discount = safe_float(offer.get("discount_percent", 0))
    min_purchase = safe_float(offer.get("min_purchase_amount", 0))
    offer_id = safe_int(offer.get("id"), 1)

    base_views = 650 + offer_id * 90 + int(discount * 18)
    redemptions = int(base_views * max(0.06, min(0.28, (discount / 100) * 0.82 + 0.05)))
    new_clients = int(redemptions * max(0.2, 0.38 - (offer_id * 0.03)))
    avg_check = 360 + discount * 11 + min_purchase * 0.07
    revenue = int(redemptions * avg_check)
    promo_cost = max(1, redemptions * avg_check * (discount / 100))
    conversion = round((redemptions / max(base_views, 1)) * 100, 1)
    roi = round(((revenue - promo_cost) / promo_cost) * 100, 0)

    return {
        "views": base_views,
        "redemptions": redemptions,
        "new_clients": new_clients,
        "revenue": revenue,
        "conversion": conversion,
        "roi": roi,
        "avg_check": avg_check,
    }


def get_offer_goal_status(offer: dict, performance: dict) -> dict:
    if not _parse_bool(offer.get("goal_enabled", False)):
        return {"enabled": False}

    metric = offer.get("goal_metric", "new_clients")
    target = safe_int(offer.get("goal_target", 0), 0)
    current = safe_float(performance.get(metric, 0), 0)
    progress = 0 if target <= 0 else min(100, int(round((current / target) * 100)))
    achieved = target > 0 and current >= target
    remaining = max(target - current, 0)
    metric_label = GOAL_METRIC_LABELS.get(metric, metric)

    return {
        "enabled": True,
        "metric": metric,
        "metric_label": metric_label,
        "target": target,
        "current": current,
        "progress": progress,
        "achieved": achieved,
        "remaining": remaining,
    }


def summarize_metrics(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "new_clients": 0,
            "revenue": 0.0,
            "transactions": 0,
            "avg_check": 0.0,
            "repeat_clients": 0,
        }

    return {
        "new_clients": int(df["new_clients"].sum()),
        "revenue": float(df["revenue"].sum()),
        "transactions": int(df["total_transactions"].sum()),
        "avg_check": float(df["average_check"].mean()),
        "repeat_clients": int(df["repeat_clients"].sum()),
    }