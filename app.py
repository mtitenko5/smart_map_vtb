import streamlit as st
import pydeck as pdk
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import os
from styles import apply_business_styles, apply_styles
import random
import string

# ─── Принудительная светлая тема (Переопределяет системные настройки) ───
def force_light_theme():
    st.markdown("""
    <style>
    :root {
        --bg-main: #f6faff;
        --bg-card: #ffffff;
        --text-main: #111827;
        --text-muted: #6b7280;
        --border-color: #e5e7eb;
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
    /* Бейджи */
    .badge { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; margin-right: 6px; vertical-align: middle; }
    .badge-fav { background: #e3f2fd !important; color: #1976d2 !important; }
    .badge-new { background: #e8f5e9 !important; color: #2e7d32 !important; }
    .badge-discount { background: linear-gradient(90deg, #5aa9ff, #7fc8ff); color: white; }
    </style>
    """, unsafe_allow_html=True)

# ─── Загрузка данных из CSV ───
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
def _load_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(path): return pd.DataFrame()
    try: return pd.read_csv(path)
    except Exception as e:
        st.error(f"Ошибка загрузки {filename}: {e}")
        return pd.DataFrame()

def _parse_bool(val) -> bool:
    if isinstance(val, bool): return val
    if isinstance(val, str): return val.strip().lower() in ('true', '1', 'yes')
    return False

def get_offer_status(valid_until_str):
    if pd.isna(valid_until_str): return 'unknown', 'Неизвестно'
    try: exp_date = pd.to_datetime(valid_until_str).date()
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
def load_transactions() -> pd.DataFrame: return _load_csv('client_transactions.csv')
def load_partners() -> list: return _load_csv('client_parthers.csv').to_dict('records')

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

# ─── Инициализация состояния приложения ───
st.set_page_config(layout="wide", page_title="ВТБ Приложение", page_icon="💙")
force_light_theme()

if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'user_type' not in st.session_state: st.session_state.user_type = None
if 'biz_auth_user' not in st.session_state: st.session_state.biz_auth_user = None

if 'biz_offers' not in st.session_state:
    st.session_state.biz_offers = get_business_offers(active_only=False)
if 'editing_offer_id' not in st.session_state:
    st.session_state.editing_offer_id = None

#Диалог активации предложения
@st.dialog("🎁 Активация предложения", width="large")
def show_activation_dialog(offer: dict):
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    
    st.markdown(f"### 🏬 {offer.get('shop', 'Партнёр')}")
    st.info(f"📍 {offer.get('address', 'Адрес не указан')}")
    st.markdown(f"**📄 Описание:** {offer.get('offer_description', 'Без описания')}")
    
    col_d1, col_d2 = st.columns(2)
    with col_d1: st.metric("💰 Ваша выгода", f"-{offer.get('discount_percent', 0)}%")
    with col_d2: st.metric("⏰ Действует до", offer.get('valid_until', '—'))
    
    st.divider()
    st.success("🔑 Покажите этот код кассиру для получения скидки:")
    st.code(code, language=None)
    st.caption("Код генерируется один раз. Сделайте скриншот или скопируйте его.")
    
    if st.button("👍 Понятно, закрыть", use_container_width=True):
        st.rerun()

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

# ─── Генерация метрик эффективности для оффера (демо-логика) ───
def get_offer_performance(offer: dict) -> dict:
    discount = float(offer.get('discount_percent', 0))
    base_views = 1200 if discount >= 15 else 800
    base_redemptions = int(base_views * (discount / 100) * 0.65)
    base_new_clients = int(base_redemptions * 0.35)
    avg_check = 450 + (discount * 12)
    revenue = int(base_redemptions * avg_check)
    return {
        "views": base_views, "redemptions": base_redemptions, "new_clients": base_new_clients,
        "revenue": revenue, "conversion": round((base_redemptions / base_views) * 100, 1),
        "roi": round(((revenue - (base_redemptions * avg_check * discount / 100)) / (base_redemptions * avg_check * discount / 100)) * 100, 0)
    }

# ─── Экран входа ───
if not st.session_state.authenticated:
    apply_business_styles()
    col_login, _, _ = st.columns([1, 2, 2])
    with col_login:
        user_mode = st.radio("Выберите тип входа:", ["Я клиент", "Я партнер"], horizontal=True, label_visibility="collapsed")
        
        if user_mode == "Я клиент":
            st.markdown('<h2 style="text-align:center;color:#002882;margin-bottom:5px;">Умная карта ВТБ</h2>', unsafe_allow_html=True)
            st.markdown("""
            <div style="text-align:center; padding: 15px; background: rgba(255,255,255,0.7); border-radius: 12px; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05);">
            Находите на карте выгодные предложения партнёров, подобранные специально для Вас, и экономьте на повседневных покупках<br/>
            </div>
            """, unsafe_allow_html=True)
            with st.form("client_login_form"):
                st.text_input("Логин", key="username", placeholder="Введите логин")
                submit = st.form_submit_button("Войти", use_container_width=True)
                if submit: login_client()
            with st.expander("Демо-доступ"): st.markdown("Логин для Марины: `bubliki`")
            
        else:
            st.markdown('<h2 style="text-align:center;color:#002882;margin-bottom:5px;">ВТБ - банк для бизнеса</h2>', unsafe_allow_html=True)
            st.markdown("""
            <div style="text-align:center; padding: 15px; background: rgba(255,255,255,0.7); border-radius: 12px; margin-bottom: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05);">
            Привлекайте новых клиентов и увеличивайте выручку с сервисом «Умная карта» от ВТБ<br/>
            </div>
            """, unsafe_allow_html=True)
            with st.form("biz_login_form"):
                st.text_input("Логин", key="biz_login_field", placeholder="Введите логин")
                submit = st.form_submit_button("Войти", use_container_width=True)
                if submit:
                    login = st.session_state.get('biz_login_field')
                    if login: login_business(login)
                    else: st.error("Введите логин")
            with st.expander("Демо-доступ"): st.markdown("Логин для Кофе Хаус: `coffee_admin`")
    st.stop()

# ─── Клиентский интерфейс ───
if st.session_state.user_type == 'client':
    apply_styles()
    df = load_transactions()
    user_shops = set(df['shop'].dropna().unique()) if not df.empty else set()
    user_cats = set(df['category'].dropna().unique()) if not df.empty else set()
    
    with st.sidebar:
        st.write("👤 Пользователь: bubliki"); st.markdown("---")
        st.info("Данные обновлены: " + datetime.now().strftime("%d.%m.%Y %H:%M"))
        if st.button("🚪 Выйти", use_container_width=True): logout()
    
    tab = st.radio("  ", ["🎁 Выгода рядом", "🗺 Мои траты", "🔔 Уведомления"], horizontal=True)

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
        #Лучшее предложение дня + Потенциальная экономия
        st.markdown("""
        <div class="card" style="background: linear-gradient(135deg, #e3f2fd 0%, #ffffff 100%); border-left: 5px solid #0055b8; padding: 20px; margin-bottom: 15px;">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                <div>
                    <h3 style="margin:0; color:#002882;">⛽ Лучшее предложение дня: АЗС Shell</h3>
                    <p style="margin:5px 0; color:#555;">Кешбэк 10% на топливо по карте ВТБ • Набережная реки Волковки, 15Б</p>
                </div>
                <span class="badge badge-discount" style="background:#0055b8; font-size:16px; padding:8px 16px;">-10%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🎟 Активировать лучшее предложение", key="act_best_offer", use_container_width=True):
            show_activation_dialog({
                "shop": "АЗС Shell",
                "address": "Набережная реки Волковки, 15Б",
                "offer_description": "Кешбэк 10% на топливо по карте ВТБ",
                "discount_percent": 10,
                "valid_until": "2026-05-18"
            })
        
        col_sav1, col_sav2 = st.columns([2, 1])
        with col_sav1:
            st.caption("📅 Расчёт за текущий месяц на основе ваших транзакций и активных партнёрских скидок")
        with col_sav2:
            # Динамический расчёт потенциальной экономии
            potential_savings = 0.0
            if not df.empty and not df['category'].empty:
                for _, offer in enumerate(load_partners()):
                    if get_offer_status(offer['valid_until'])[0] != 'expired':
                        mask = df['category'].str.contains(offer['category'], case=False, na=False)
                        cat_amount = df[mask]['amount'].sum() if mask.any() else 0
                        potential_savings += cat_amount * (float(offer['discount_percent']) / 100)
            st.metric("💰 Потенциальная экономия", f"₽{int(potential_savings):,}")
        all_offers = load_partners()
        if all_offers:
            active_offers = [o for o in all_offers if get_offer_status(o['valid_until'])[0] != "expired"]
            
            # Подготовка бейджей
            for offer in active_offers:
                is_fav = offer.get('shop') in user_shops
                is_cat_match = offer.get('category') in user_cats
                offer['badge_html'] = ""
                if is_fav:
                    offer['badge_html'] += '<span class="badge badge-fav">❤️ Любимое место</span>'
                elif is_cat_match and not is_fav:
                    # Отмечаем как "новенькое", если ещё не набрали 2
                    pass

            # Добавляем 2 "новеньких" если нужно, или маркируем первые 2 совпавшие по категории
            new_candidates = [o for o in active_offers if not o.get('shop') in user_shops and o.get('category') in user_cats]
            for i, o in enumerate(new_candidates[:2]):
                o['badge_html'] += '<span class="badge badge-new">✨ Что-то новенькое</span>'

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
                    st.markdown(f"""<div class="card">
                    <div style="display:flex;justify-content:space-between;align-items:center; flex-wrap:wrap; gap:8px;">
                        <div><b>🏬 {offer['shop']}</b> {offer.get('badge_html', '')} <span class="badge badge-discount">-{offer['discount_percent']}%</span></div>
                        <div style="font-size:14px;color:#666;">{status_text}</div>
                    </div>
                    <div style="margin-top:10px;">🎁 {offer['offer_description']}</div>
                    <div style="margin-top:5px;font-size:12px;color:#888;">📍 {offer['address']} | ⏰ До: {offer['valid_until']}</div>
                    </div>""", unsafe_allow_html=True)

                    # Кнопка активации с вызовом диалога
                    if st.button("🎟 Активировать предложение", key=f"act_{offer['id']}", use_container_width=True):
                        show_activation_dialog(offer)
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
# ─── Бизнес-интерфейс ───
elif st.session_state.user_type == 'business':
    apply_business_styles()
    summary = get_business_summary()
    
    with st.sidebar:
        st.markdown(f"""☕ {summary['business_name']} Средний бизнес ⭐ {summary['rating']} ({summary['total_reviews']} отзывов)""", unsafe_allow_html=True)
        st.markdown("---")
        menu = st.radio("Меню", ["Дашборд", "Предложения", "Отзывы", "Уведомления"], label_visibility="collapsed")
        st.markdown("---")
        st.caption(f"{datetime.now().strftime('%d.%m.%Y %H:%M')}")
        if st.button("🚪 Выйти", use_container_width=True): logout()

    if menu == "Дашборд":
        st.markdown('<div class="header-gradient"><h2 style="margin:0;">Панель управления</h2><p style="margin:5px 0 0 0;">Обзор показателей за 30 дней</p></div>', unsafe_allow_html=True)
        
        # Основные метрики
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.markdown(f"""<div class="metric-card"><div class="metric-label">Новых клиентов</div><div class="metric-value">{int(summary['new_clients']):,}</div><div class="metric-trend">↑ 23% за месяц</div></div>""", unsafe_allow_html=True)
        with col2: st.markdown(f"""<div class="metric-card"><div class="metric-label">Выручка</div><div class="metric-value">₽{int(summary['revenue']):,}</div><div class="metric-trend">↑ 15% за месяц</div></div>""", unsafe_allow_html=True)
        with col3: st.markdown(f"""<div class="metric-card"><div class="metric-label">Транзакций</div><div class="metric-value">{int(summary['transactions']):,}</div><div class="metric-trend">↑ 12% за месяц</div></div>""", unsafe_allow_html=True)
        with col4: st.markdown(f"""<div class="metric-card"><div class="metric-label">Средний чек</div><div class="metric-value">₽{int(summary['avg_check']):,}</div><div class="metric-trend">↑ 5% за месяц</div></div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 💡 Выгода от сотрудничества с ВТБ")
        bank_metrics = {
            "🤝 Клиентов привлечено через ВТБ": f"{int(summary['new_clients'] * 0.68):,}",
            "📈 Рост среднего чека": "+18.4%",
            "📉 Экономия на внешней рекламе": f"₽{int(summary['revenue'] * 0.12):,}",
            "🔄 Возвратность клиентов": "72%",
        }
        cols_bm = st.columns(2)
        for i, (label, value) in enumerate(bank_metrics.items()):
            with cols_bm[i % 2]:
                st.markdown(f"""<div class="card" style="text-align:center; border-left: 4px solid #0055b8;">
                <div style="font-size:14px; color:#666; margin-bottom:5px;">{label}</div>
                <div style="font-size:20px; font-weight:bold; color:#002882;">{value}</div>
                </div>""", unsafe_allow_html=True)

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
        st.markdown('<div class="header-gradient"><h2 style="margin:0;">Управление предложениями</h2><p style="margin:5px 0 0 0;">Создание, редактирование и аналитика эффективности</p></div>', unsafe_allow_html=True)
        
       # ЗАПРОС 1: Исправлена форма (убран on_click у form_submit_button)
        with st.expander("➕ Создать / ✏️ Редактировать предложение", expanded=st.session_state.editing_offer_id is not None):
            editing_id = st.session_state.editing_offer_id
            current = next((o for o in st.session_state.biz_offers if o['id'] == editing_id), {}) if editing_id else {}
        
            # ⚠️ ВАЖНО: st.form_submit_button ОБЯЗАН находиться ВНУТРИ with st.form()
            with st.form("offer_form", clear_on_submit=False):
                c1, c2 = st.columns(2)
                title = c1.text_input("Название акции", value=current.get("title", ""))
                category = c2.selectbox("Категория", ["Напитки", "Еда", "Обеды", "Завтраки", "Розница", "Услуги"],
                                    index=0 if not current else ["Напитки", "Еда", "Обеды", "Завтраки", "Розница", "Услуги"].index(current.get("category", "Еда")))
            
                desc = st.text_area("Описание", value=current.get("description", ""))
                d1, d2, d3 = st.columns(3)
                discount = d1.number_input("Скидка (%)", min_value=1, max_value=99, value=current.get("discount_percent", 10))
                min_sum = d2.number_input("Мин. сумма покупки (₽)", min_value=0, value=current.get("min_purchase_amount", 500))
                valid_until = d3.date_input("Действует до", value=datetime.strptime(current.get("valid_until", "2026-12-31"), "%Y-%m-%d").date() if current.get("valid_until") else datetime.now() + timedelta(days=30))
            
                is_active = st.checkbox("Активно", value=current.get("is_active", True) if current else True)
                submit_clicked = st.form_submit_button("💾 Сохранить предложение", use_container_width=True)

            if editing_id:
                if st.button("❌ Отменить редактирование", use_container_width=True):
                    st.session_state.editing_offer_id = None
                    st.rerun()
        
            # Обработка нажатия
            if submit_clicked:
                new_offer = {
                "id": editing_id if editing_id else max((o["id"] for o in st.session_state.biz_offers), default=0) + 1,
                "title": title, "description": desc, "discount_percent": discount,
                "valid_from": datetime.now().strftime("%Y-%m-%d"),
                "valid_until": valid_until.strftime("%Y-%m-%d"),
                "category": category, "min_purchase_amount": min_sum,
                "usage_count": current.get("usage_count", 0), "is_active": is_active
                }
                if editing_id:
                    idx = next((i for i, o in enumerate(st.session_state.biz_offers) if o["id"] == editing_id), None)
                    if idx is not None: st.session_state.biz_offers[idx] = new_offer
                else:
                    st.session_state.biz_offers.append(new_offer)
                st.session_state.editing_offer_id = None
                st.success("✅ Предложение сохранено!")
                st.rerun()

        st.markdown("### Ваши активные предложения и их эффективность")
        offers = [o for o in st.session_state.biz_offers if o.get("is_active", False)]
        
        if not offers:
            st.info("📭 Пока нет активных предложений. Создайте первое выше 👆")
        else:
            for offer in offers:
                status, status_text = get_offer_status(offer['valid_until'])
                perf = get_offer_performance(offer)
                
                col_main, col_actions = st.columns([4, 1])
                with col_main:
                    st.markdown(f"""<div class="offer-card" style="margin-bottom:15px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div><h3 style="margin:0;color:#002882;">{offer['title']}</h3><p style="margin:8px 0;color:#666;">{offer['description']}</p></div>
                        <span class="offer-badge">-{offer['discount_percent']}%</span>
                    </div>
                    <div style="margin-top:15px;padding-top:15px;border-top:1px solid #e0e0e0;font-size:13px;color:#888;">
                    🧁 {offer['category']} | 💰 От {offer['min_purchase_amount']} руб. | 📅 {status_text}
                    </div>
                    </div>""", unsafe_allow_html=True)
                    
                    # Метрики эффективности предложения
                    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
                    mc1.metric("👁 Показов", f"{perf['views']:,}")
                    mc2.metric("✅ Активаций", f"{perf['redemptions']:,}")
                    mc3.metric("🆕 Новых клиентов", f"+{perf['new_clients']}")
                    mc4.metric("💰 Оборот", f"₽{perf['revenue']:,}")
                    mc5.metric("📈 Конверсия", f"{perf['conversion']}%")
                
                with col_actions:
                    st.button("✏️", key=f"edit_{offer['id']}", help="Редактировать", use_container_width=True, on_click=lambda oid=offer['id']: setattr(st.session_state, 'editing_offer_id', oid))
                    st.button("🗑", key=f"del_{offer['id']}", help="Удалить", use_container_width=True, on_click=lambda oid=offer['id']: setattr(st.session_state, 'biz_offers', [o for o in st.session_state.biz_offers if o['id'] != oid]))

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
