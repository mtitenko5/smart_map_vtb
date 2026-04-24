import math
import os
import random
import string
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

from styles import apply_business_styles, apply_styles

from logic import (
    _parse_bool,
    safe_float,
    safe_int,
    format_money,
    haversine_km,
    estimate_distance_text,
    get_offer_status,
    get_filtered_data,
    compute_period_delta,
    get_monthly_average_spend,
    get_offer_performance,
    get_offer_goal_status,
    summarize_metrics,
)


# ─── Принудительная светлая тема (Переопределяет системные настройки) ───
def force_light_theme():
    st.markdown(
        """
    <style>
    :root {
        --bg-main: #f6faff;
        --bg-card: #ffffff;
        --text-main: #111827;
        --text-muted: #6b7280;
        --border-color: #e5e7eb;
        --accent: #0055b8;
        --success-soft: #eaf8ef;
        --warning-soft: #fff8e7;
        --purple-soft: #f3edff;
    }
    html, body, .stApp, .stApp > header, .stApp > div, .st-emotion-cache-1dp5vir, .st-emotion-cache-1l4v61, [data-testid="stSidebar"] {
        background-color: var(--bg-main) !important;
        color: var(--text-main) !important;
    }
    @media (prefers-color-scheme: dark) {
        body, .stApp, .st-emotion-cache-1dp5vir, .st-emotion-cache-1l4v61 {
            background-color: var(--bg-main) !important;
            color: var(--text-main) !important;
        }
        .stTextInput > div > div > input, .stNumberInput > div > div > input, .stTextArea textarea {
            background-color: var(--bg-card) !important;
            color: var(--text-main) !important;
            border: 1px solid var(--border-color) !important;
        }
        .stSelectbox > div > div > div, .stDateInput > div > div > div > div, .stCheckbox > label > div {
            background-color: var(--bg-card) !important;
            color: var(--text-main) !important;
        }
    }
    .badge { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; margin-right: 6px; vertical-align: middle; }
    .badge-fav { background: #e3f2fd !important; color: #1976d2 !important; }
    .badge-new { background: #e8f5e9 !important; color: #2e7d32 !important; }
    .badge-discount { background: linear-gradient(90deg, #5aa9ff, #7fc8ff); color: white; }
    .badge-reason { background: #f1f5f9; color: #334155; }
    .why-box {
        background: linear-gradient(135deg, #f8fbff 0%, #eef6ff 100%);
        border: 1px solid #dbeafe;
        border-radius: 16px;
        padding: 12px 14px;
        margin: 10px 0 12px 0;
        color: #1e3a8a;
    }
    .details-box {
        background: rgba(255,255,255,0.88);
        border: 1px solid #e5eef8;
        border-radius: 16px;
        padding: 14px;
        margin-top: 8px;
    }
    .section-caption {
        color: #607086;
        font-size: 13px;
        margin-top: -4px;
        margin-bottom: 10px;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CLIENT_LOCATION = {"lat": 59.9343, "lon": 30.3351}
GOAL_METRIC_LABELS = {
    "new_clients": "новые клиенты",
    "redemptions": "активации",
    "revenue": "выручка",
}
GOAL_METRIC_OPTIONS = {
    "Новые клиенты": "new_clients",
    "Активации": "redemptions",
    "Выручка": "revenue",
}
REVERSE_GOAL_OPTIONS = {v: k for k, v in GOAL_METRIC_OPTIONS.items()}


def _load_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as e:
        st.error(f"Ошибка загрузки {filename}: {e}")
        return pd.DataFrame()

# ─── Клиентские данные ───
def load_transactions() -> pd.DataFrame:
    df = _load_csv("client_transactions.csv")
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def load_partners() -> list:
    df = _load_csv("client_parthers.csv")
    if df.empty:
        return []
    df["is_active"] = df["is_active"].apply(_parse_bool)
    return df.to_dict("records")


# ─── Бизнес-данные ───
def authenticate_business(login: str) -> dict | None:
    df = _load_csv("business_users.csv")
    if df.empty:
        return None
    match = df[df["login"] == login]
    return match.iloc[0].to_dict() if not match.empty else None


def get_business_summary(days=30) -> dict:
    df_user = _load_csv("business_users.csv")
    df_metrics = _load_csv("business_metrics.csv")
    if df_user.empty:
        return {
            "business_name": "Бизнес",
            "rating": 0.0,
            "total_reviews": 0,
            "new_clients": 0,
            "revenue": 0.0,
            "transactions": 0,
            "avg_check": 0.0,
        }
    user = df_user.iloc[0].to_dict()
    if df_metrics.empty:
        user.update({"new_clients": 0, "revenue": 0.0, "transactions": 0, "avg_check": 0.0})
        return user

    m = pd.DataFrame(get_business_metrics(days=days))
    if m.empty:
        user.update({"new_clients": 0, "revenue": 0.0, "transactions": 0, "avg_check": 0.0})
        return user

    user.update(
        {
            "new_clients": int(m["new_clients"].sum()),
            "revenue": float(m["revenue"].sum()),
            "transactions": int(m["total_transactions"].sum()),
            "avg_check": round(m["average_check"].mean(), 2),
        }
    )
    return user


def ensure_offer_defaults(offers: list[dict]) -> list[dict]:
    default_goal_settings = {
        1: {"goal_enabled": True, "goal_metric": "new_clients", "goal_target": 80},
        2: {"goal_enabled": True, "goal_metric": "redemptions", "goal_target": 90},
        3: {"goal_enabled": True, "goal_metric": "revenue", "goal_target": 60000},
    }
    enriched = []
    for idx, raw_offer in enumerate(offers, start=1):
        offer = dict(raw_offer)
        offer["id"] = safe_int(offer.get("id"), idx)
        offer["discount_percent"] = safe_float(offer.get("discount_percent"), 0)
        offer["min_purchase_amount"] = safe_int(offer.get("min_purchase_amount"), 0)
        offer["usage_count"] = safe_int(offer.get("usage_count"), 0)
        offer["is_active"] = _parse_bool(offer.get("is_active", True))

        defaults = default_goal_settings.get(offer["id"], {})
        offer["goal_enabled"] = _parse_bool(offer.get("goal_enabled", defaults.get("goal_enabled", False)))
        offer["goal_metric"] = offer.get("goal_metric", defaults.get("goal_metric", "new_clients"))
        offer["goal_target"] = safe_int(offer.get("goal_target", defaults.get("goal_target", 50)), 50)
        enriched.append(offer)
    return enriched


def get_business_offers(active_only=True) -> list:
    df = _load_csv("business_offers.csv")
    if df.empty:
        return []
    df["is_active"] = df["is_active"].apply(_parse_bool)
    offers = ensure_offer_defaults(df.to_dict("records"))
    if active_only:
        today = datetime.now().strftime("%Y-%m-%d")
        offers = [o for o in offers if o["is_active"] and str(o.get("valid_until", "")) >= today]
    return offers


def get_business_metrics(days=30) -> list:
    df = _load_csv("business_metrics.csv")
    if df.empty:
        return []
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    return df.tail(days).to_dict("records")


def get_business_reviews(limit=10) -> list:
    df = _load_csv("business_reviews.csv")
    if df.empty:
        return []
    df["created_at"] = pd.to_datetime(df["created_at"])
    return df.sort_values("created_at", ascending=False).head(limit).to_dict("records")



# ─── Логика рекомендаций для клиента ───
def get_client_reference_location(df: pd.DataFrame) -> tuple[float, float]:
    if df.empty:
        return DEFAULT_CLIENT_LOCATION["lat"], DEFAULT_CLIENT_LOCATION["lon"]
    last_txn = df.sort_values("date").iloc[-1]
    return safe_float(last_txn.get("lat"), DEFAULT_CLIENT_LOCATION["lat"]), safe_float(
        last_txn.get("lon"), DEFAULT_CLIENT_LOCATION["lon"]
    )


def build_offer_recommendation(offer: dict, transactions_df: pd.DataFrame) -> dict:
    category = offer.get("category", "")
    shop = offer.get("shop", "")
    shop_txn = transactions_df[transactions_df["shop"] == shop] if not transactions_df.empty else pd.DataFrame()
    cat_txn = transactions_df[transactions_df["category"] == category] if not transactions_df.empty else pd.DataFrame()

    monthly_spend = get_monthly_average_spend(transactions_df, category)
    estimated_savings = monthly_spend * safe_float(offer.get("discount_percent"), 0) / 100

    if not shop_txn.empty:
        visits = len(shop_txn)
        reason_title = "❤️ Любимое место"
        reason_text = f"Вы уже {visits} раз(а) платили в {shop}. Поэтому предложение показывается выше остальных." 
    elif len(cat_txn) >= 3:
        reason_title = "📍 Подходит под ваши траты"
        reason_text = f"У вас {len(cat_txn)} покупок в категории «{category}». Это предложение совпадает с вашими привычными расходами."
    else:
        reason_title = "✨ Что-то новенькое"
        reason_text = f"Это новый партнёр рядом с вами в категории «{category}», который может заменить часть ваших обычных трат."

    savings_text = ""
    if estimated_savings > 0:
        savings_text = f"При похожем ритме трат можно сэкономить около {format_money(estimated_savings)} в месяц."

    return {
        "reason_title": reason_title,
        "reason_text": reason_text,
        "estimated_savings": estimated_savings,
        "savings_text": savings_text,
    }


def get_offer_payment_rules(offer: dict) -> list[str]:
    category = str(offer.get("category", "")).lower()
    if "азс" in category:
        return [
            "Оплата только картой ВТБ",
            "Предложение действует на топливо и сопутствующие товары",
            "Не суммируется с корпоративными скидками",
        ]
    if "аптек" in category:
        return [
            "Оплата только картой ВТБ",
            "Скидка не действует на рецептурные препараты",
            "Можно использовать в розничной точке партнёра",
        ]
    if "кафе" in category or "ресторан" in category:
        return [
            "Оплата только картой ВТБ",
            "Акция действует на позиции из меню партнёра",
            "Не суммируется с другими акциями заведения",
        ]
    return [
        "Оплата только картой ВТБ",
        "Действует в магазине партнёра",
        "Не суммируется с другими скидками",
    ]


def get_offer_color(offer: dict, recommendation: dict) -> tuple[str, str]:
    title = recommendation.get("reason_title", "")
    if "Любимое" in title:
        return "#0ea5e9", "#eff6ff"
    if "Подходит" in title:
        return "#10b981", "#f0fdf4"
    return "#8b5cf6", "#faf5ff"


def get_offer_detail_items(offer: dict, transactions_df: pd.DataFrame) -> list[str]:
    ref_lat, ref_lon = get_client_reference_location(transactions_df)
    category = offer.get("category", "категория")
    rules = get_offer_payment_rules(offer)
    detail_items = [
        f"📍 Адрес: {offer.get('address', 'Адрес уточняется')}",
        f"🧭 Расстояние: {estimate_distance_text(offer.get('lat'), offer.get('lon'), ref_lat, ref_lon)}",
        f"💳 Способ оплаты: {rules[0]}",
        f"🛒 Категория: {category}",
        f"⏰ Срок действия: до {offer.get('valid_until', '—')}",
        f"ℹ️ Ограничения: {rules[1]}",
        f"➕ Дополнительно: {rules[2]}",
    ]
    return detail_items


# ─── Бизнес-аналитика ───
def build_offer_ranking(offers: list[dict]) -> list[dict]:
    ranked = []
    for offer in offers:
        perf = get_offer_performance(offer)
        goal = get_offer_goal_status(offer, perf)
        ranked.append({"offer": offer, "performance": perf, "goal": goal})
    return ranked


def sort_ranked_offers(ranked_offers: list[dict], mode: str) -> list[dict]:
    if mode == "Самое прибыльное сверху":
        return sorted(ranked_offers, key=lambda x: x["performance"]["revenue"], reverse=True)
    if mode == "Самое слабое сверху":
        return sorted(ranked_offers, key=lambda x: x["performance"]["revenue"])
    if mode == "Лучшая конверсия":
        return sorted(ranked_offers, key=lambda x: x["performance"]["conversion"], reverse=True)
    return ranked_offers


def build_business_notifications(offers: list[dict]) -> list[dict]:
    base_df = _load_csv("notifications.csv")
    notifications = []
    if not base_df.empty:
        notifications.extend(base_df.to_dict("records"))

    for offer in offers:
        perf = get_offer_performance(offer)
        goal = get_offer_goal_status(offer, perf)
        if not goal.get("enabled"):
            continue
        if goal["achieved"]:
            notifications.append(
                {
                    "title": f"Цель по акции «{offer['title']}» достигнута",
                    "message": f"План по метрике «{goal['metric_label']}» выполнен: {int(goal['current'])} из {goal['target']}.",
                    "type": "success",
                }
            )
        else:
            notifications.append(
                {
                    "title": f"Прогресс по акции «{offer['title']}»",
                    "message": f"До цели по метрике «{goal['metric_label']}» осталось {int(goal['remaining'])}. Сейчас выполнено {goal['progress']}%.",
                    "type": "info",
                }
            )

    notifications.append(
        {
            "title": "Как считаются новые клиенты",
            "message": "Банк считает новоым клиентом держателя карты, который активировал предложение и оплатил у партнёра впервые за выбранный период.",
            "type": "info",
        }
    )
    return notifications


def get_metrics_with_comparison(days: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = _load_csv("business_metrics.csv")
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    current = df.tail(days).copy()
    previous = df.iloc[max(0, len(df) - 2 * days) : max(0, len(df) - days)].copy()
    return df, current, previous


# ─── Инициализация состояния приложения ───
st.set_page_config(layout="wide", page_title="ВТБ Приложение", page_icon="💙")
force_light_theme()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_type" not in st.session_state:
    st.session_state.user_type = None
if "biz_auth_user" not in st.session_state:
    st.session_state.biz_auth_user = None
if "selected_client_offer_id" not in st.session_state:
    st.session_state.selected_client_offer_id = None
if "biz_offers" not in st.session_state:
    st.session_state.biz_offers = ensure_offer_defaults(get_business_offers(active_only=False))
if "editing_offer_id" not in st.session_state:
    st.session_state.editing_offer_id = None


# ─── Диалог активации предложения ───
@st.dialog("🎁 Активация предложения", width="large")
def show_activation_dialog(offer: dict):
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
    st.markdown(f"### 🏬 {offer.get('shop', offer.get('title', 'Партнёр'))}")
    st.info(f"📍 {offer.get('address', 'Адрес не указан')}")
    st.markdown(f"**📄 Описание:** {offer.get('offer_description', offer.get('description', 'Без описания'))}")

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.metric("💰 Ваша выгода", f"-{safe_int(offer.get('discount_percent', 0))}%")
    with col_d2:
        st.metric("⏰ Действует до", offer.get("valid_until", "—"))

    st.divider()
    st.success("🔑 Покажите этот код кассиру для получения скидки:")
    st.code(code, language=None)
    st.caption("Код генерируется один раз. Сделайте скриншот или скопируйте его.")

    if st.button("👍 Понятно, закрыть", use_container_width=True):
        st.rerun()


# ─── Авторизация ───
def login_client():
    if st.session_state.get("username") == "bubliki":
        st.session_state.authenticated = True
        st.session_state.user_type = "client"
        st.rerun()
    st.error("Неверный логин")


def login_business(login: str):
    user = authenticate_business(login)
    if user:
        st.session_state.authenticated = True
        st.session_state.user_type = "business"
        st.session_state.biz_auth_user = login
        st.rerun()
    st.error("Неверный логин")


def logout():
    st.session_state.authenticated = False
    st.session_state.user_type = None
    st.session_state.biz_auth_user = None
    st.session_state.selected_client_offer_id = None
    st.rerun()


# ─── Экран входа ───
if not st.session_state.authenticated:
    apply_business_styles()
    col_login, _, _ = st.columns([1, 2, 2])
    with col_login:
        user_mode = st.radio(
            "Выберите тип входа:",
            ["Для клиента", "Для бизнеса"],
            horizontal=True,
            label_visibility="collapsed",
        )

        if user_mode == "Для клиента":
            st.markdown(
                '<h2 style="text-align:center;color:#002882;margin-bottom:5px;">Умная карта ВТБ</h2>',
                unsafe_allow_html=True,
            )
            st.markdown(
                """
            <div style="text-align:center; padding: 15px; background: rgba(255,255,255,0.7); border-radius: 12px; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05);">
            Находите на карте выгодные предложения партнёров, подобранные специально для Вас, и экономьте на повседневных покупках<br/>
            </div>
            """,
                unsafe_allow_html=True,
            )
            with st.form("client_login_form"):
                st.text_input("Логин", key="username", placeholder="Введите логин")
                submit = st.form_submit_button("Войти", use_container_width=True)
                if submit:
                    login_client()
            with st.expander("Демо-доступ"):
                st.markdown("Логин для Марины: `bubliki`")

        else:
            st.markdown(
                '<h2 style="text-align:center;color:#002882;margin-bottom:5px;">ВТБ - банк для бизнеса</h2>',
                unsafe_allow_html=True,
            )
            st.markdown(
                """
            <div style="text-align:center; padding: 15px; background: rgba(255,255,255,0.7); border-radius: 12px; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05);">
            Привлекайте новых клиентов и увеличивайте выручку с сервисом «Умная карта» от ВТБ<br/>
            </div>
            """,
                unsafe_allow_html=True,
            )
            with st.form("biz_login_form"):
                st.text_input("Логин", key="biz_login_field", placeholder="Введите логин")
                submit = st.form_submit_button("Войти", use_container_width=True)
                if submit:
                    login = st.session_state.get("biz_login_field")
                    if login:
                        login_business(login)
                    else:
                        st.error("Введите логин")
            with st.expander("Демо-доступ"):
                st.markdown("Логин для Кофе Хаус: `coffee_admin`")
    st.stop()


# ─── Клиентский интерфейс ───
if st.session_state.user_type == "client":
    apply_styles()
    df = load_transactions()
    user_shops = set(df["shop"].dropna().unique()) if not df.empty else set()
    user_cats = set(df["category"].dropna().unique()) if not df.empty else set()

    col_c1, col_c2 = st.columns([2, 1])
    with col_c1:
        st.markdown("**Пользователь: bubliki**")
    with col_c2:
        if st.button("🚪 Выйти", key="client_logout_top", use_container_width=True):
            logout()
    st.markdown("---")

    tab = st.radio("  ", ["🎁 Выгода рядом", "🗺 Мои траты", "🔔 Уведомления"], horizontal=True)

    if tab == "🗺 Мои траты":
        st.markdown("## 💙 Карта моих трат")
        categories = ["Все"] + list(df["category"].unique()) if not df.empty else ["Все"]
        col1, col2, col3 = st.columns(3)
        with col1:
            category = st.selectbox("Категория трат", categories)
        with col2:
            start_date = st.date_input("📅 С", datetime.now() - timedelta(days=30))
        with col3:
            end_date = st.date_input("📅 По", datetime.now())

        df_filtered = get_filtered_data(df, category, start_date, end_date)
        if not df_filtered.empty:
            df_filtered = df_filtered.copy()
            df_filtered["date_str"] = pd.to_datetime(df_filtered["date"]).dt.strftime("%d.%m.%Y %H:%M")
            max_amt = df_filtered["amount"].max()
            df_filtered["radius"] = (df_filtered["amount"] / max_amt) * 500 if max_amt > 0 else 500

            layer = pdk.Layer(
                "ScatterplotLayer",
                data=df_filtered,
                get_position="[lon, lat]",
                get_radius="radius",
                get_fill_color=[0, 40, 130, 180],
                pickable=True,
            )
            view = pdk.ViewState(latitude=59.9343, longitude=30.3351, zoom=11, pitch=30)
            st.pydeck_chart(
                pdk.Deck(
                    map_style="light",
                    initial_view_state=view,
                    layers=[layer],
                    tooltip={
                        "html": "<b>🏬 {shop}</b><br>📂 {category}<br>💰 {amount} ₽<br>📅 {date_str}",
                        "style": {"backgroundColor": "#fff", "color": "#002882", "borderRadius": "8px"},
                    },
                )
            )

            col_stat1, col_stat2, col_stat3 = st.columns(3)
            with col_stat1:
                st.metric("💸 Всего трат", f"{int(df_filtered['amount'].sum()):,} ₽".replace(",", " "))
            with col_stat2:
                st.metric("🛒 Транзакций", len(df_filtered))
            with col_stat3:
                st.metric("📍 Любимых магазинов", df_filtered["shop"].nunique())

            st.markdown("### 📋 Детализация транзакций")
            st.dataframe(
                df_filtered[["date", "shop", "category", "amount"]].sort_values("date", ascending=False),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("🙁 Нет данных за выбранный период")

    elif tab == "🎁 Выгода рядом":
        st.markdown("## 🎁 Выгодные предложения партнёров")
        st.markdown(
            """
        <div class="card" style="background: linear-gradient(135deg, #e3f2fd 0%, #ffffff 100%); border-left: 5px solid #0055b8; padding: 20px; margin-bottom: 15px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                <div>
                    <h3 style="margin:0; color:#002882;">⛽ Лучшее предложение дня: АЗС Shell</h3>
                    <p style="margin:5px 0; color:#555;">Кешбэк 10% на топливо по карте ВТБ • Набережная реки Волковки, 15Б</p>
                </div>
                <span class="badge badge-discount" style="background:#0055b8; font-size:16px; padding:8px 16px;">-10%</span>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )
        if st.button("🎟 Активировать лучшее предложение", key="act_best_offer", use_container_width=True):
            show_activation_dialog(
                {
                    "shop": "АЗС Shell",
                    "address": "Набережная реки Волковки, 15Б",
                    "offer_description": "Кешбэк 10% на топливо по карте ВТБ",
                    "discount_percent": 10,
                    "valid_until": "2026-05-18",
                }
            )

        col_sav1, col_sav2 = st.columns([2, 1])
        with col_sav1:
            st.caption("📅 Оценка строится на ваших прошлых тратах и текущих скидках партнёров")
        with col_sav2:
            potential_savings = 0.0
            for offer in load_partners():
                if get_offer_status(offer.get("valid_until"))[0] == "expired":
                    continue
                potential_savings += get_monthly_average_spend(df, offer.get("category", "")) * (
                    safe_float(offer.get("discount_percent", 0)) / 100
                )
            st.metric("💰 Потенциальная экономия", format_money(potential_savings))

        all_offers = load_partners()
        if all_offers:
            active_offers = [o for o in all_offers if _parse_bool(o.get("is_active", True)) and get_offer_status(o.get("valid_until"))[0] != "expired"]
            enriched_offers = []
            for offer in active_offers:
                recommendation = build_offer_recommendation(offer, df)
                badge_html = ""
                if offer.get("shop") in user_shops:
                    badge_html += '<span class="badge badge-fav">❤️ Любимое место</span>'
                elif offer.get("category") in user_cats:
                    badge_html += '<span class="badge badge-new">🎯 По вашим тратам</span>'
                else:
                    badge_html += '<span class="badge badge-new">✨ Что-то новенькое</span>'
                offer["badge_html"] = badge_html
                offer["recommendation"] = recommendation
                enriched_offers.append(offer)

            st.markdown(f"### ✅ Активных предложений {len(enriched_offers)}")
            selected_offer = next(
                (o for o in enriched_offers if o.get("id") == st.session_state.selected_client_offer_id),
                None,
            )
            if selected_offer:
                st.info(f"На карте центр смещён к партнёру: {selected_offer['shop']}")
                map_lat = safe_float(selected_offer.get("lat"), DEFAULT_CLIENT_LOCATION["lat"])
                map_lon = safe_float(selected_offer.get("lon"), DEFAULT_CLIENT_LOCATION["lon"])
                map_zoom = 13
            else:
                map_lat, map_lon = DEFAULT_CLIENT_LOCATION["lat"], DEFAULT_CLIENT_LOCATION["lon"]
                map_zoom = 11

            df_offers = pd.DataFrame(enriched_offers)
            if not df_offers.empty:
                df_offers = df_offers.copy()
                df_offers["valid_until_str"] = pd.to_datetime(df_offers["valid_until"]).dt.strftime("%d.%m.%Y")
                df_offers["marker_color"] = df_offers["shop"].apply(
                    lambda shop: [0, 85, 184, 230]
                    if not selected_offer or shop != selected_offer.get("shop")
                    else [16, 185, 129, 240]
                )
                offer_layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=df_offers,
                    get_position="[lon, lat]",
                    get_radius=500,
                    get_fill_color="marker_color",
                    pickable=True,
                )
                view = pdk.ViewState(latitude=map_lat, longitude=map_lon, zoom=map_zoom, pitch=28)
                st.pydeck_chart(
                    pdk.Deck(
                        map_style="light",
                        initial_view_state=view,
                        layers=[offer_layer],
                        tooltip={
                            "html": "<div style='padding:10px;'><b>🏬 {shop}</b><br/>🎁 {offer_description}<br/>💰 Выгода: {discount_percent}%<br/>📅 До: {valid_until_str}</div>",
                            "style": {"backgroundColor": "#ffffff", "color": "#28a745", "borderRadius": "8px"},
                        },
                    )
                )

            for offer in enriched_offers:
                status, status_text = get_offer_status(offer["valid_until"])
                recommendation = offer["recommendation"]
                border_color, bg_color = get_offer_color(offer, recommendation)
                savings_text = recommendation["savings_text"]
                description = offer.get("offer_description", "")
                details = get_offer_detail_items(offer, df)

                st.markdown(
                    f"""
                    <div class="card" style="border-left:6px solid {border_color}; background:{bg_color}; margin-bottom:8px;">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;">
                            <div style="flex:1;min-width:280px;">
                                <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                                    <b style="font-size:18px; color:#0f172a;">🏬 {offer['shop']}</b>
                                    {offer.get('badge_html', '')}
                                    <span class="badge badge-discount">-{safe_int(offer['discount_percent'])}%</span>
                                </div>
                                <div style="margin-top:8px; color:#334155;">🎁 {description}</div>
                                <div class="why-box">
                                    <div style="font-weight:700; margin-bottom:4px;">{recommendation['reason_title']}</div>
                                    <div>{recommendation['reason_text']}</div>
                                    {f'<div style="margin-top:6px;">💡 {savings_text}</div>' if savings_text else ''}
                                </div>
                                <div style="font-size:12px;color:#64748b;">📍 {offer['address']} • ⏰ {status_text}</div>
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                btn_col1, btn_col2 = st.columns([1, 1])
                with btn_col1:
                    if st.button("📍 Показать на карте", key=f"show_map_{offer['id']}", use_container_width=True):
                        st.session_state.selected_client_offer_id = offer["id"]
                        st.rerun()
                with btn_col2:
                    if st.button("🎟 Активировать предложение", key=f"act_{offer['id']}", use_container_width=True):
                        show_activation_dialog(offer)

                with st.expander(f"Подробнее о предложении {offer['shop']}"):
                    for item in details:
                        st.markdown(f"- {item}")
                    if savings_text:
                        st.caption(f"Личная оценка выгоды: {savings_text}")

        else:
            st.info("📭 В данный момент нет активных предложений")

    elif tab == "🔔 Уведомления":
        st.markdown("## 🔔 Уведомления")
        notifications = [
            ("💰", "Вы часто тратите на кафе, партнеры рядом могут помочь сэкономить до 500 ₽ в месяц.", "active"),
            ("🎉", "Попробуйте новый партнёрский магазин с детскими товарами рядом с вашими обычными маршрутами.", "active"),
            ("🚗", "АЗС Shell подходит под ваши регулярные траты на топливо — скидка действует до конца месяца.", "active"),
            ("⚠️", "Не упустите предложения с истекающим сроком в разделе 'Выгода рядом'.", "warning"),
            ("📊", "За последние 30 дней ваши траты на супермаркеты были ниже обычного на 12%.", "info"),
        ]
        for icon, text, type_ in notifications:
            if type_ == "warning":
                st.warning(f"{icon} {text}")
            elif type_ == "info":
                st.info(f"{icon} {text}")
            else:
                st.markdown(f"""<div class="card">{icon} {text}</div>""", unsafe_allow_html=True)


# ─── Бизнес-интерфейс ───
elif st.session_state.user_type == "business":
    apply_business_styles()
    summary = get_business_summary(days=30)

    col_b1, col_b2, col_b3 = st.columns([3, 2, 1])
    with col_b1:
        st.markdown(
            f"☕ **{summary['business_name']}** | Малый бизнес | ⭐ {summary['rating']} ({summary['total_reviews']} отзывов)"
        )
    with col_b2:
        st.caption(f"🕒 Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    with col_b3:
        if st.button("🚪 Выйти", key="biz_logout_top", use_container_width=True):
            logout()
    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs(["Дашборд", "Предложения", "Отзывы", "Уведомления"])

    with tab1:
        st.markdown(
            '<div class="header-gradient"><h2 style="margin:0;">Панель управления</h2><p style="margin:5px 0 0 0;">Следите за динамикой по периодам и сравнивайте результаты</p></div>',
            unsafe_allow_html=True,
        )

        period_label = st.radio("Период анализа", ["7 дней", "30 дней"], horizontal=True)
        period_days = 7 if period_label == "7 дней" else 30
        _, current_df, previous_df = get_metrics_with_comparison(period_days)
        current_summary = summarize_metrics(current_df)
        previous_summary = summarize_metrics(previous_df)

        current_header = f"Обзор за последние {period_days} дней"
        if not current_df.empty:
            current_header += f" • {current_df['date'].min().strftime('%d.%m')} - {current_df['date'].max().strftime('%d.%m')}"
        st.caption(current_header)

        metrics_data = [
            ("Новых клиентов", current_summary["new_clients"], previous_summary["new_clients"]),
            ("Выручка", current_summary["revenue"], previous_summary["revenue"]),
            ("Транзакций", current_summary["transactions"], previous_summary["transactions"]),
            ("Средний чек", current_summary["avg_check"], previous_summary["avg_check"]),
        ]
        col1, col2, col3, col4 = st.columns(4)
        for col, (label, current_value, prev_value) in zip([col1, col2, col3, col4], metrics_data):
            trend_text, delta_value = compute_period_delta(current_value, prev_value)
            formatted_value = format_money(current_value) if label in {"Выручка", "Средний чек"} else f"{int(round(current_value)):,}".replace(",", " ")
            with col:
                st.markdown(
                    f"""
                    <div class="metric-card">
                        <div class="metric-label">{label}</div>
                        <div class="metric-value">{formatted_value}</div>
                        <div class="metric-trend">{trend_text}</div>
                        <div class="metric-sub">Прошлый период: {format_money(prev_value) if label in {'Выручка', 'Средний чек'} else f'{int(round(prev_value)):,}'.replace(',', ' ')}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("---")
        st.markdown("### 💡 Выгода от сотрудничества с ВТБ")
        bank_metrics = {
            "🤝 Клиентов привлечено через ВТБ": f"{int(current_summary['new_clients'] * 0.68):,}".replace(",", " "),
            "📈 Рост среднего чека": compute_period_delta(current_summary["avg_check"], previous_summary["avg_check"])[1],
            "📉 Экономия на внешней рекламе": format_money(current_summary["revenue"] * 0.12),
            "🔄 Возвратность клиентов": f"{int((current_summary['repeat_clients'] / max(current_summary['transactions'], 1)) * 100)}%",
        }
        cols_bm = st.columns(2)
        for i, (label, value) in enumerate(bank_metrics.items()):
            with cols_bm[i % 2]:
                st.markdown(
                    f"""
                    <div class="card" style="text-align:center; border-left: 4px solid #0055b8;">
                        <div style="font-size:14px; color:#666; margin-bottom:5px;">{label}</div>
                        <div style="font-size:20px; font-weight:bold; color:#002882;">{value}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("---")
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.markdown("### Выручка по дням")
            metrics = get_business_metrics(days=30)
            if metrics:
                df_m = pd.DataFrame(metrics)
                df_m["date"] = pd.to_datetime(df_m["date"])
                fig = px.line(df_m, x="date", y="revenue", markers=True, line_shape="spline")
                fig.update_layout(
                    xaxis_title="Дата",
                    yaxis_title="Выручка, руб.",
                    margin=dict(t=20, l=20, r=20, b=20),
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)

        with col_chart2:
            st.markdown("### Клиенты")
            if metrics:
                df_m = pd.DataFrame(metrics)
                df_m["date"] = pd.to_datetime(df_m["date"])
                fig = px.bar(
                    df_m,
                    x="date",
                    y=["new_clients", "repeat_clients"],
                    labels={"value": "Клиенты", "variable": "Тип"},
                    barmode="stack",
                )
                fig.update_layout(
                    margin=dict(t=20, l=20, r=20, b=20),
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.markdown(
            '<div class="header-gradient"><h2 style="margin:0;">Управление предложениями</h2><p style="margin:5px 0 0 0;">Создание, редактирование, цели и аналитика эффективности</p></div>',
            unsafe_allow_html=True,
        )

        with st.expander(
            "➕ Создать / ✏️ Редактировать предложение",
            expanded=st.session_state.editing_offer_id is not None,
        ):
            editing_id = st.session_state.editing_offer_id
            current = next(
                (o for o in st.session_state.biz_offers if safe_int(o.get("id")) == safe_int(editing_id)),
                {},
            ) if editing_id else {}

            cur_discount = safe_int(current.get("discount_percent", 10), 10)
            cur_min_sum = safe_int(current.get("min_purchase_amount", 500), 500)
            goal_enabled_default = _parse_bool(current.get("goal_enabled", True if not editing_id else False))
            goal_metric_default = current.get("goal_metric", "new_clients")
            goal_target_default = safe_int(current.get("goal_target", 50), 50)

            try:
                cur_valid_until = datetime.strptime(
                    str(current.get("valid_until", "2026-12-31")), "%Y-%m-%d"
                ).date()
            except Exception:
                cur_valid_until = (datetime.now() + timedelta(days=30)).date()

            with st.form("offer_form", clear_on_submit=False):
                c1, c2 = st.columns(2)
                title = c1.text_input("Название акции", value=current.get("title", ""))

                cat_list = ["Напитки", "Еда", "Обеды", "Завтраки", "Розница", "Услуги"]
                default_cat = current.get("category", "Еда")
                cat_idx = cat_list.index(default_cat) if default_cat in cat_list else 0
                category = c2.selectbox("Категория", cat_list, index=cat_idx)

                desc = st.text_area("Описание", value=current.get("description", ""))
                d1, d2, d3 = st.columns(3)
                discount = d1.number_input("Скидка (%)", min_value=1, max_value=99, value=cur_discount, step=1)
                min_sum = d2.number_input("Мин. сумма покупки (₽)", min_value=0, value=cur_min_sum, step=10)
                valid_until = d3.date_input("Действует до", value=cur_valid_until)

                is_active = st.checkbox("Активно", value=_parse_bool(current.get("is_active", True)))

                st.markdown("### 🎯 Цель по акции")
                st.caption("Цель привязана к конкретному предложению, чтобы её прогресс был виден в карточке оффера и уведомлениях.")
                goal_enabled = st.checkbox("Добавить цель для этой акции", value=goal_enabled_default)
                goal_col1, goal_col2 = st.columns(2)
                with goal_col1:
                    goal_metric_label = st.selectbox(
                        "Метрика цели",
                        list(GOAL_METRIC_OPTIONS.keys()),
                        index=list(GOAL_METRIC_OPTIONS.values()).index(goal_metric_default)
                        if goal_metric_default in GOAL_METRIC_OPTIONS.values()
                        else 0,
                        disabled=not goal_enabled,
                    )
                with goal_col2:
                    goal_target = st.number_input(
                        "Целевое значение",
                        min_value=1,
                        value=goal_target_default,
                        step=5,
                        disabled=not goal_enabled,
                    )

                submit_clicked = st.form_submit_button("💾 Сохранить предложение", use_container_width=True)

            if editing_id:
                if st.button("❌ Отменить редактирование", use_container_width=True):
                    st.session_state.editing_offer_id = None
                    st.rerun()

            if submit_clicked:
                next_id = max((safe_int(o.get("id")) for o in st.session_state.biz_offers), default=0) + 1
                new_offer = {
                    "id": editing_id if editing_id else next_id,
                    "title": title,
                    "description": desc,
                    "discount_percent": safe_int(discount),
                    "valid_from": current.get("valid_from", datetime.now().strftime("%Y-%m-%d")),
                    "valid_until": valid_until.strftime("%Y-%m-%d"),
                    "category": category,
                    "min_purchase_amount": safe_int(min_sum),
                    "usage_count": current.get("usage_count", 0),
                    "is_active": is_active,
                    "goal_enabled": goal_enabled,
                    "goal_metric": GOAL_METRIC_OPTIONS[goal_metric_label],
                    "goal_target": safe_int(goal_target),
                }
                if editing_id:
                    idx = next(
                        (i for i, o in enumerate(st.session_state.biz_offers) if safe_int(o.get("id")) == safe_int(editing_id)),
                        None,
                    )
                    if idx is not None:
                        st.session_state.biz_offers[idx] = new_offer
                else:
                    st.session_state.biz_offers.append(new_offer)
                st.session_state.editing_offer_id = None
                st.success("✅ Предложение сохранено!")
                st.rerun()

        active_offers = [o for o in st.session_state.biz_offers if _parse_bool(o.get("is_active", False))]
        ranked_offers = build_offer_ranking(active_offers)

        if ranked_offers:
            best_offer = max(ranked_offers, key=lambda x: x["performance"]["revenue"])
            worst_offer = min(ranked_offers, key=lambda x: x["performance"]["revenue"])
            hi_col1, hi_col2 = st.columns(2)
            with hi_col1:
                st.markdown(
                    f"""
                    <div class="card" style="border-left:4px solid #16a34a;">
                        <div style="font-size:14px;color:#64748b;">Самое прибыльное предложение</div>
                        <div style="font-size:20px;font-weight:700;color:#0f172a;">{best_offer['offer']['title']}</div>
                        <div style="margin-top:6px;color:#166534;">Оборот: {format_money(best_offer['performance']['revenue'])} • Конверсия: {best_offer['performance']['conversion']}%</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with hi_col2:
                st.markdown(
                    f"""
                    <div class="card" style="border-left:4px solid #dc2626;">
                        <div style="font-size:14px;color:#64748b;">Самое слабое предложение</div>
                        <div style="font-size:20px;font-weight:700;color:#0f172a;">{worst_offer['offer']['title']}</div>
                        <div style="margin-top:6px;color:#991b1b;">Оборот: {format_money(worst_offer['performance']['revenue'])} • Конверсия: {worst_offer['performance']['conversion']}%</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("### Ваши активные предложения и их эффективность")
        sort_mode = st.selectbox(
            "Сортировка списка",
            ["По умолчанию", "Самое прибыльное сверху", "Самое слабое сверху", "Лучшая конверсия"],
        )
        ranked_offers = sort_ranked_offers(ranked_offers, sort_mode)

        if not ranked_offers:
            st.info("📭 Пока нет активных предложений. Создайте первое выше 👆")
        else:
            for ranked in ranked_offers:
                offer = ranked["offer"]
                perf = ranked["performance"]
                goal = ranked["goal"]
                status, status_text = get_offer_status(offer["valid_until"])

                col_main, col_actions = st.columns([4, 1])
                with col_main:
                    st.markdown(
                        f"""
                        <div class="offer-card" style="margin-bottom:15px;">
                            <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;">
                                <div>
                                    <h3 style="margin:0;color:#002882;">{offer['title']}</h3>
                                    <p style="margin:8px 0;color:#475569;">{offer['description']}</p>
                                </div>
                                <span class="offer-badge">-{safe_int(offer['discount_percent'])}%</span>
                            </div>
                            <div style="margin-top:15px;padding-top:15px;border-top:1px solid #e0e0e0;font-size:13px;color:#64748b;">
                                🧁 {offer['category']} | 💰 От {safe_int(offer['min_purchase_amount'])} ₽ | 📅 {status_text}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
                    mc1.metric("👁 Показов", f"{perf['views']:,}".replace(",", " "))
                    mc2.metric("✅ Активаций", f"{perf['redemptions']:,}".replace(",", " "))
                    mc3.metric("🆕 Новых клиентов", f"+{perf['new_clients']}")
                    mc4.metric("💰 Оборот", format_money(perf['revenue']))
                    mc5.metric("📈 Конверсия", f"{perf['conversion']}%")

                    if goal.get("enabled"):
                        st.progress(goal["progress"] / 100)
                        if goal["achieved"]:
                            st.success(
                                f"Цель по метрике «{goal['metric_label']}» достигнута: {int(goal['current'])} из {goal['target']}."
                            )
                        else:
                            st.info(
                                f"Цель: {goal['metric_label']} — {int(goal['current'])} из {goal['target']} ({goal['progress']}%)."
                            )
                    else:
                        st.caption("Для этого предложения цель не задана.")

                with col_actions:
                    if st.button("✏️", key=f"edit_{offer['id']}", help="Редактировать", use_container_width=True):
                        st.session_state.editing_offer_id = offer["id"]
                        st.rerun()
                    if st.button("🗑", key=f"del_{offer['id']}", help="Удалить", use_container_width=True):
                        st.session_state.biz_offers = [o for o in st.session_state.biz_offers if safe_int(o.get("id")) != safe_int(offer["id"])]
                        st.rerun()

    with tab3:
        st.markdown(
            '<div class="header-gradient"><h2 style="margin:0;">⭐ Отзывы клиентов</h2><p style="margin:5px 0 0 0;">Рейтинг и обратная связь</p></div>',
            unsafe_allow_html=True,
        )
        reviews = get_business_reviews(limit=10)
        for review in reviews:
            stars = "⭐ " * safe_int(review["rating"]) + "☆ " * (5 - safe_int(review["rating"]))
            st.markdown(
                f"""
                <div class="review-card">
                    <div style="display:flex;justify-content:space-between;">
                        <div>
                            <div class="star-rating">{stars}</div>
                            <b>{review['client_name']}</b>
                            <div style="font-size:13px;color:#888;">{str(review['created_at'])[:10]}</div>
                        </div>
                    </div>
                    <p style="margin:10px 0;">{review['comment']}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with tab4:
        st.markdown(
            '<div class="header-gradient"><h2 style="margin:0;">🔔 Уведомления</h2><p style="margin:5px 0 0 0;">Важные сообщения от ВТБ и прогресс по акциям</p></div>',
            unsafe_allow_html=True,
        )
        notifications = build_business_notifications(st.session_state.biz_offers)
        for notif in notifications:
            notif_type = notif.get("type", "info")
            if notif_type == "success":
                st.success(f"✅ **{notif['title']}**: {notif['message']}")
            elif notif_type == "warning":
                st.warning(f"⚠️ **{notif['title']}**: {notif['message']}")
            else:
                st.info(f"ℹ️ **{notif['title']}**: {notif['message']}")
