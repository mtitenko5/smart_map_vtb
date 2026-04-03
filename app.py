import streamlit as st
import pydeck as pdk
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import os

from styles import (apply_business_styles, apply_styles)

# ─── Загрузка данных из CSV (заменяет db.py / queries.py / business_db.py) ───
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _load_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path):
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as e:
        st.error(f"Ошибка загрузки {filename}: {e}")
        return pd.DataFrame()

def _parse_bool(val) -> bool:
    if isinstance(val, bool): return val
    if isinstance(val, str): return val.strip().lower() in ('true', '1', 'yes')
    return False

def get_offer_status(valid_until_str):
    if pd.isna(valid_until_str): return 'unknown', 'Неизвестно'
    try:
        exp_date = pd.to_datetime(valid_until_str).date()
    except Exception: return 'unknown', 'Неизвестно'
    
    today = datetime.now().date()
    days_left = (exp_date - today).days
    if days_left < 0: return 'expired', f'Истёк {abs(days_left)} дн. назад'
    if days_left == 0: return 'active', 'Истекает сегодня'
    if days_left <= 3: return 'soon', f'Осталось {days_left} дн.'
    return 'active', f'Осталось {days_left} дн.'

def get_filtered_data(df: pd.DataFrame, category: str, start_date, end_date) -> pd.DataFrame:
    if df.empty: return pd.DataFrame()
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    mask = (df['date'] >= pd.to_datetime(start_date)) & (df['date'] <= pd.to_datetime(end_date))
    if category != 'Все': mask &= (df['category'] == category)
    return df[mask].reset_index(drop=True)

# Клиентские данные
def load_transactions() -> pd.DataFrame: return _load_csv('transactions.csv')
def load_partners() -> list: return _load_csv('client_partners.csv').to_dict('records')

# Бизнес-данные
def authenticate_business(login: str) -> dict | None:
    df = _load_csv('business_users.csv')
    if df.empty: return None
    match = df[df['login'] == login]
    return match.iloc[0].to_dict() if not match.empty else None

def get_business_summary() -> dict:
    df_user = _load_csv('business_users.csv')
    df_metrics = _load_csv('business_metrics.csv')
    if df_user.empty:
        return {'business_name': 'Бизнес', 'rating': 0.0, 'total_reviews': 0, 'new_clients': 0, 'revenue': 0.0, 'transactions': 0, 'avg_check': 0.0}
    
    user = df_user.iloc[0].to_dict()
    if df_metrics.empty:
        user.update({'new_clients': 0, 'revenue': 0.0, 'transactions': 0, 'avg_check': 0.0})
    else:
        m = df_metrics.tail(30)
        user.update({
            'new_clients': int(m['new_clients'].sum()),
            'revenue': float(m['revenue'].sum()),
            'transactions': int(m['total_transactions'].sum()),
            'avg_check': round(m['average_check'].mean(), 2)
        })
    return user

def get_business_offers(active_only=True) -> list:
    df = _load_csv('business_offers.csv')
    if df.empty: return []
    if active_only:
        df = df[df['is_active'].apply(_parse_bool)]
        df = df[df['valid_until'] >= datetime.now().strftime('%Y-%m-%d')]
    return df.to_dict('records')

def get_business_metrics(days=30) -> list:
    df = _load_csv('business_metrics.csv')
    if df.empty: return []
    df['date'] = pd.to_datetime(df['date'])
    return df.sort_values('date').tail(days).to_dict('records')

def get_business_reviews(limit=10) -> list:
    df = _load_csv('business_reviews.csv')
    if df.empty: return []
    df['created_at'] = pd.to_datetime(df['created_at'])
    return df.sort_values('created_at', ascending=False).head(limit).to_dict('records')

def get_business_notifications() -> list:
    return _load_csv('notifications.csv').to_dict('records')

# ─── Настройки и Сессия ───
st.set_page_config(layout="wide", page_title="ВТБ Приложение", page_icon="💙")
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'user_type' not in st.session_state: st.session_state.user_type = None
if 'biz_auth_user' not in st.session_state: st.session_state.biz_auth_user = None

def login_client():
    if st.session_state.get('username') == 'bubliki':
        st.session_state.authenticated = True; st.session_state.user_type = 'client'; st.rerun()
    else: st.error('Неверный логин')

def login_business(login: str):
    user = authenticate_business(login)
    if user:
        st.session_state.authenticated = True; st.session_state.user_type = 'business'
        st.session_state.biz_auth_user = login; st.rerun()
    else: st.error('Неверный логин')

def logout():
    st.session_state.authenticated = False; st.session_state.user_type = None
    st.session_state.biz_auth_user = None; st.rerun()

# ─── Экран входа ───
if not st.session_state.authenticated:
    apply_business_styles()
    col_login, _, _ = st.columns([1, 2, 2])
    with col_login:
        user_mode = st.radio("Выберите тип входа:", ["Я клиент", "Я партнер"], horizontal=True, label_visibility="collapsed")
        if user_mode == "Я клиент":
            st.markdown('<div class="header-gradient"><h2 style="margin:0;">Умная карта ВТБ</h2></div>', unsafe_allow_html=True)
            st.markdown("<div style='text-align:left;font-size:12px;color:#666;margin:20px 0;'>☑️ Я согласен на обработку персональных данных и доступ к информации о транзакциях</div>", unsafe_allow_html=True)
            with st.form("client_login_form"):
                st.text_input("Логин", key="username", placeholder="Введите логин")
                submit = st.form_submit_button("Войти", use_container_width=True)
                if submit: login_client()
            with st.expander("Демо-доступ"): st.markdown("**Логин для Марины:** `bubliki`")
        else:
            st.markdown('<div class="header-gradient"><h2 style="margin:0;">ВТБ - банк для бизнеса</h2></div>', unsafe_allow_html=True)
            with st.form("biz_login_form"):
                st.text_input("Логин", key="biz_login_field", placeholder="Введите логин")
                submit = st.form_submit_button("Войти", use_container_width=True)
                if submit:
                    login = st.session_state.get('biz_login_field')
                    if login: login_business(login)
                    else: st.error("Введите логин")
            with st.expander("Демо-доступ"): st.markdown("**Логин для Кофе Хаус:** `coffee_admin`")
    st.stop()

if st.session_state.user_type == 'client':
    apply_styles()
    with st.sidebar:
        st.write("👤 Пользователь: bubliki"); st.markdown("---")
        st.info("Данные обновлены: " + datetime.now().strftime("%d.%m.%Y %H:%M"))
        if st.button("🚪 Выйти", use_container_width=True): logout()

    tab = st.radio(" ", ["🎁 Выгода рядом", "🗺 Мои траты", "🔔 Уведомления"], horizontal=True)
    df = load_transactions()

    if tab == "🗺 Мои траты":
        st.markdown("## 💙 Карта моих трат")
        categories = ["Все"] + list(df["category"].unique()) if not df.empty else ["Все"]
        col1, col2, col3 = st.columns(3)
        with col1: category = st.selectbox("Категория трат", categories)
        with col2: start_date = st.date_input("📅 С", datetime.now() - timedelta(days=30))
        with col3: end_date = st.date_input("📅 По", datetime.now())

        df_filtered = get_filtered_data(df, category, start_date, end_date)
        if not df_filtered.empty:
            df_filtered = df_filtered.copy()
            df_filtered["date_str"] = pd.to_datetime(df_filtered["date"]).dt.strftime("%d.%m.%Y %H:%M")
            max_amt = df_filtered["amount"].max()
            df_filtered["radius"] = (df_filtered["amount"] / max_amt) * 500 if max_amt > 0 else 500

            layer = pdk.Layer("ScatterplotLayer", data=df_filtered, get_position='[lon, lat]', get_radius="radius", get_fill_color=[0, 40, 130, 180], pickable=True)
            view = pdk.ViewState(latitude=59.9343, longitude=30.3351, zoom=11, pitch=30)
            st.pydeck_chart(pdk.Deck(map_style='light', initial_view_state=view, layers=[layer], tooltip={"html": "<b>🏬 {shop}</b><br>📂 {category}<br>💰 {amount} ₽<br>📅 {date_str}", "style": {"backgroundColor": "#fff", "color": "#002882", "borderRadius": "8px"}}))

            col_stat1, col_stat2, col_stat3 = st.columns(3)
            with col_stat1: st.metric("💸 Всего трат", f"{int(df_filtered['amount'].sum()):,} ₽")
            with col_stat2: st.metric("🛒 Транзакций", len(df_filtered))
            with col_stat3: st.metric("📍 Любимых магазинов", df_filtered['shop'].nunique())

            st.markdown("### 📋 Детализация транзакций")
            st.dataframe(df_filtered[['date', 'shop', 'category', 'amount']].sort_values('date', ascending=False), use_container_width=True, hide_index=True)
        else: st.info("🙁 Нет данных за выбранный период")

    elif tab == "🎁 Выгода рядом":
        st.markdown("## 🎁 Выгодные предложения партнёров")
        all_offers = load_partners()
        if all_offers:
            active_offers = [o for o in all_offers if get_offer_status(o['valid_until'])[0] != "expired"]
            expired_offers = [o for o in all_offers if get_offer_status(o['valid_until'])[0] == "expired"]

            st.markdown(f"### ✅ Активных предложений {len(active_offers)}")
            if active_offers:
                df_offers = pd.DataFrame(active_offers)
                if not df_offers.empty:
                    df_offers = df_offers.copy()
                    df_offers["valid_until_str"] = pd.to_datetime(df_offers["valid_until"]).dt.strftime("%d.%m.%Y")
                    offer_layer = pdk.Layer("ScatterplotLayer", data=df_offers, get_position='[lon, lat]', get_radius=500, get_fill_color=[0, 200, 100, 200], pickable=True)
                    view = pdk.ViewState(latitude=59.9343, longitude=30.3351, zoom=11, pitch=30)
                    st.pydeck_chart(pdk.Deck(map_style='light', initial_view_state=view, layers=[offer_layer], tooltip={"html": "<div style='padding:10px;'><b>🏬 {shop}</b><br/>🎁 {offer_description}<br/>💰 Выгода: {discount_percent}%<br/>📅 До: {valid_until_str}</div>", "style": {"backgroundColor": "#ffffff", "color": "#28a745", "borderRadius": "8px"}}))

                for offer in active_offers:
                    status, status_text = get_offer_status(offer['valid_until'])
                    st.markdown(f"""<div class="card"><div style="display:flex;justify-content:space-between;align-items:center;"><div><b>🏬 {offer['shop']}</b><span class="badge badge-discount">-{offer['discount_percent']}%</span></div><div style="font-size:14px;color:#666;">{status_text}</div></div><div style="margin-top:10px;">🎁 {offer['offer_description']}</div><div style="margin-top:5px;font-size:12px;color:#888;">📍 {offer['address']} | ⏰ До: {offer['valid_until']}</div></div>""", unsafe_allow_html=True)

            if expired_offers:
                with st.expander(f"🕒 Истёкшие предложения ({len(expired_offers)})"):
                    for offer in expired_offers:
                        _, status_text = get_offer_status(offer['valid_until'])
                        st.markdown(f"""<div class="card"><b>🏬 {offer['shop']}</b> - {offer['discount_percent']}%<br/>{offer['offer_description']}<br/><small style="color:#888;">{status_text}</small></div>""", unsafe_allow_html=True)
        else: st.info("📭 В данный момент нет активных предложений")

    elif tab == "🔔 Уведомления":
        st.markdown("## 🔔 Уведомления")
        notifications = [
            ("💰", "Ты бы мог сэкономить на обедах 925 рублей, питаясь правильно с доставкой от Самокат", "active"),
            ("🎉", "Больше товаров для детей в магазине Motherbear с кешбэком до 10%", "active"),
            ("🚗", "В FitService получите 2% кешбэк за первую покупку по карте ВТБ", "active"),
            ("⚠️", "Не упустите выгодные предложения в разделе 'Выгода рядом'", "warning"),
            ("📊", "В марте Вы потратили на 32% меньше, чем в феврале", "info")
        ]
        for icon, text, type_ in notifications:
            if type_ == "warning": st.warning(f"{icon} {text}")
            elif type_ == "info": st.info(f"{icon} {text}")
            else: st.markdown(f"""<div class="card">{icon} {text}</div>""", unsafe_allow_html=True)

        categories = ["Все"] + list(df["category"].unique()) if not df.empty else ["Все"]
        col1, col2, col3 = st.columns(3)
        with col1: category = st.selectbox("Категория трат", categories)
        with col2: start_date = st.date_input("📅 С", datetime.now() - timedelta(days=30))
        with col3: end_date = st.date_input("📅 По", datetime.now())

        df_filtered = get_filtered_data(df, category, start_date, end_date)
        if not df_filtered.empty:
            st.markdown("### 📊 Итоги периода")
            col1, col2 = st.columns(2)
            with col1: st.metric("Траты", f"{int(df_filtered['amount'].sum()):,} ₽")
            with col2: st.metric("Средний кешбэк (5%)", f"{int(df_filtered['amount'].sum() * 0.05):,} ₽")

elif st.session_state.user_type == 'business':
    apply_business_styles()
    summary = get_business_summary()
    with st.sidebar:
        st.markdown(f"""☕<br>{summary['business_name']}<br>Средний бизнес<br>⭐ {summary['rating']} ({summary['total_reviews']} отзывов)""", unsafe_allow_html=True)
        st.markdown("---")
        menu = st.radio("Меню", ["Дашборд", "Предложения", "Отзывы", "Уведомления"], label_visibility="collapsed")
        st.markdown("---")
        st.caption(f"{datetime.now().strftime('%d.%m.%Y %H:%M')}")
        if st.button("🚪 Выйти", use_container_width=True): logout()

    if menu == "Дашборд":
        st.markdown('<div class="header-gradient"><h2 style="margin:0;">Панель управления</h2><p style="margin:5px 0 0 0;">Обзор показателей за 30 дней</p></div>', unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.markdown(f"""<div class="metric-card"><div class="metric-label">Новых клиентов</div><div class="metric-value">{int(summary['new_clients']):,}</div><div class="metric-trend">↑ 23% за месяц</div></div>""", unsafe_allow_html=True)
        with col2: st.markdown(f"""<div class="metric-card"><div class="metric-label">Выручка</div><div class="metric-value">₽{int(summary['revenue']):,}</div><div class="metric-trend">↑ 15% за месяц</div></div>""", unsafe_allow_html=True)
        with col3: st.markdown(f"""<div class="metric-card"><div class="metric-label">Транзакций</div><div class="metric-value">{int(summary['transactions']):,}</div><div class="metric-trend">↑ 12% за месяц</div></div>""", unsafe_allow_html=True)
        with col4: st.markdown(f"""<div class="metric-card"><div class="metric-label">Средний чек</div><div class="metric-value">₽{int(summary['avg_check']):,}</div><div class="metric-trend">↑ 5% за месяц</div></div>""", unsafe_allow_html=True)
        st.markdown("---")

        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.markdown("### Выручка по дням")
            metrics = get_business_metrics(days=30)
            if metrics:
                df_m = pd.DataFrame(metrics); df_m['date'] = pd.to_datetime(df_m['date'])
                fig = px.line(df_m, x='date', y='revenue', markers=True, line_shape='spline')
                fig.update_layout(xaxis_title='Дата', yaxis_title='Выручка, руб.', margin=dict(t=20,l=20,r=20,b=20), plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)
        with col_chart2:
            st.markdown("### Клиенты")
            if metrics:
                df_m = pd.DataFrame(metrics); df_m['date'] = pd.to_datetime(df_m['date'])
                fig = px.bar(df_m, x='date', y=['new_clients', 'repeat_clients'], labels={'value': 'Клиенты', 'variable': 'Тип'}, barmode='stack')
                fig.update_layout(margin=dict(t=20,l=20,r=20,b=20), plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)

    elif menu == "Предложения":
        st.markdown('<div class="header-gradient"><h2 style="margin:0;">Активные предложения</h2><p style="margin:5px 0 0 0;">Управление предложениями для клиентов ВТБ</p></div>', unsafe_allow_html=True)
        offers = get_business_offers(active_only=True)
        for offer in offers:
            st.markdown(f"""<div class="offer-card"><div style="display:flex;justify-content:space-between;align-items:center;"><div><h3 style="margin:0;color:#002882;">{offer['title']}</h3><p style="margin:8px 0;color:#666;">{offer['description']}</p></div><div style="text-align:right;"><span class="offer-badge">-{offer['discount_percent']}%</span></div></div><div style="margin-top:15px;padding-top:15px;border-top:1px solid #e0e0e0;font-size:13px;color:#888;">🧁 {offer['category']} | 💰 От {offer['min_purchase_amount']} руб.</div></div>""", unsafe_allow_html=True)

    elif menu == "Отзывы":
        st.markdown('<div class="header-gradient"><h2 style="margin:0;">⭐ Отзывы клиентов</h2><p style="margin:5px 0 0 0;">Рейтинг и обратная связь</p></div>', unsafe_allow_html=True)
        reviews = get_business_reviews(limit=10)
        for review in reviews:
            stars = "⭐ " * review['rating'] + "☆ " * (5 - review['rating'])
            st.markdown(f"""<div class="review-card"><div style="display:flex;justify-content:space-between;"><div><div class="star-rating">{stars}</div><b>{review['client_name']}</b><div style="font-size:13px;color:#888;">{str(review['created_at'])[:10]}</div></div></div><p style="margin:10px 0;">{review['comment']}</p></div>""", unsafe_allow_html=True)

    elif menu == "Уведомления":
        st.markdown('<div class="header-gradient"><h2 style="margin:0;">🔔 Уведомления</h2><p style="margin:5px 0 0 0;">Важные сообщения от ВТБ</p></div>', unsafe_allow_html=True)
        notifications = get_business_notifications()
        for notif in notifications:
            if notif['type'] == 'success': st.success(f"✅ **{notif['title']}**: {notif['message']}")
            elif notif['type'] == 'warning': st.warning(f"⚠️ **{notif['title']}**: {notif['message']}")
            else: st.info(f"ℹ️ **{notif['title']}**: {notif['message']}")
