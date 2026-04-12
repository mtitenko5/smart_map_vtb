import streamlit as st
import pydeck as pdk
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import os
from styles import apply_business_styles, apply_styles

# Принудительная светлая тема на уровне конфига
try: st.config.set_option('theme.base', 'light')
except Exception: pass

# ─── Загрузка данных ───
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
    except: return 'unknown', 'Неизвестно'
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

def load_transactions() -> pd.DataFrame: return _load_csv('client_transactions.csv')
def load_partners() -> list: return _load_csv('client_parthers.csv').to_dict('records')
def load_business_offers() -> list: return _load_csv('business_offers.csv').to_dict('records')

# ─── Бизнес-логика ───
def authenticate_business(login: str) -> dict | None:
    df = _load_csv('business_users.csv')
    if df.empty: return None
    match = df[df['login'] == login]
    return match.iloc[0].to_dict() if not match.empty else None

def get_business_summary() -> dict:
    df_user = _load_csv('business_users.csv')
    df_metrics = _load_csv('business_metrics.csv')
    base = {'business_name': 'Партнёр', 'rating': 4.8, 'total_reviews': 142, 'new_clients': 0, 'revenue': 0.0, 'transactions': 0, 'avg_check': 0.0}
    if df_user.empty: return base
    user = df_user.iloc[0].to_dict()
    if df_metrics.empty:
        user.update(base)
    else:
        m = df_metrics.tail(30)
        user.update({
            'new_clients': int(m['new_clients'].sum()),
            'revenue': float(m['revenue'].sum()),
            'transactions': int(m['total_transactions'].sum()),
            'avg_check': round(m['average_check'].mean(), 2)
        })
    return user

# ─── Инициализация состояния ───
st.set_page_config(layout="wide", page_title="ВТБ Приложение", page_icon="💙")
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'user_type' not in st.session_state: st.session_state.user_type = None
if 'biz_auth_user' not in st.session_state: st.session_state.biz_auth_user = None
if 'session_offers' not in st.session_state: st.session_state.session_offers = []

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

# ─── ЭКРАН ВХОДА (3. UX-тексты) ───
if not st.session_state.authenticated:
    apply_business_styles()
    col_login, _, _ = st.columns([1, 2, 2])
    with col_login:
        user_mode = st.radio("Выберите тип входа:", ["Я клиент", "Я партнер"], horizontal=True, label_visibility="collapsed")
        if user_mode == "Я клиент":
            st.markdown('<div class="vtb-title">Умная карта ВТБ</div>', unsafe_allow_html=True)
            st.markdown('<p class="ux-text">Находите на карте выгодные предложения партнёров, подобранные специально для Вас, и экономьте больше с помощью сервиса «Умная карта ВТБ»</p>', unsafe_allow_html=True)
            st.markdown("☑️ Я согласен на обработку персональных данных и доступ к информации о транзакциях", unsafe_allow_html=True)
            with st.form("client_login_form"):
                st.text_input("Логин", key="username", placeholder="Введите логин (bubliki)")
                if st.form_submit_button("Войти", use_container_width=True): login_client()
        else:
            st.markdown('<div class="vtb-title">ВТБ — банк для бизнеса</div>', unsafe_allow_html=True)
            st.markdown('<p class="ux-text">Привлекайте новых клиентов, повышайте средний чек и увеличивайте выручку с помощью программы лояльности и персонализированных предложений от ВТБ</p>', unsafe_allow_html=True)
            with st.form("biz_login_form"):
                st.text_input("Логин", key="biz_login_field", placeholder="Введите логин (coffee_admin)")
                if st.form_submit_button("Войти", use_container_width=True):
                    if st.session_state.biz_login_field: login_business(st.session_state.biz_login_field)
                    else: st.error("Введите логин")
    st.stop()

# ─── КЛИЕНТСКИЙ ИНТЕРФЕЙС ───
if st.session_state.user_type == 'client':
    apply_styles()
    with st.sidebar:
        st.write("👤 Пользователь: bubliki"); st.markdown("---")
        st.info("Данные обновлены: " + datetime.now().strftime("%d.%m.%Y %H:%M"))
        if st.button("🚪 Выйти", use_container_width=True): logout()

    df = load_transactions()
    partners = load_partners()
    shops_in_history = df['shop'].unique().tolist() if not df.empty else []

    # 4. Лучшее предложение дня & Потенциальная экономия
    st.markdown("## 🎯 Лучшие предложения для вас")
    today = datetime.now().date()
    valid_today = [p for p in partners if p.get('valid_until') and pd.to_datetime(p['valid_until']).date() >= today]
    
    # Выбираем заправку (Shell) или макс. скидку
    best_offer = next((p for p in valid_today if 'Shell' in p.get('shop', '')), valid_today[0] if valid_today else None)
    
    col_off, col_sav = st.columns([2, 1])
    with col_off:
        if best_offer:
            st.markdown(f"""
            <div class="card offer-active" style="display:flex; align-items:center; gap:15px;">
                <div style="font-size:40px;">⛽</div>
                <div>
                    <div style="font-weight:bold; font-size:18px; color:#002882;">{best_offer['shop']} — Лучшее сегодня!</div>
                    <div style="margin-top:4px;">🎁 {best_offer['offer_description']}</div>
                    <div class="badge badge-discount">-{best_offer['discount_percent']}%</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else: st.info("Сегодня нет активных спецпредложений")

    with col_sav:
        total_spent = df['amount'].sum() if not df.empty else 0
        cashback = total_spent * 0.05
        offer_save = best_offer['discount_percent'] * 50 if best_offer else 0 # Примерная экономия
        potential_sav = cashback + offer_save
        st.markdown(f"""
        <div class="card" style="text-align:center; background:linear-gradient(135deg, #e0f2fe, #bae6fd);">
            <div style="color:#0369a1; font-size:14px; font-weight:600;">💰 Ваша выгода в этом месяце</div>
            <div style="font-size:32px; font-weight:bold; color:#002882; margin:10px 0;">{int(potential_sav):,} ₽</div>
            <div style="font-size:12px; color:#0369a1;">Кешбэк 5% + активные скидки</div>
        </div>
        """, unsafe_allow_html=True)

    tab = st.radio(" ", ["🗺 Мои траты", "🎁 Выгода рядом", "🔔 Уведомления"], horizontal=True)

    if tab == "🗺 Мои траты":
        st.markdown("## 💙 Карта моих трат")
        categories = ["Все"] + list(df["category"].unique()) if not df.empty else ["Все"]
        c1, c2, c3 = st.columns(3)
        with c1: category = st.selectbox("Категория трат", categories)
        with c2: start_date = st.date_input("📅 С", datetime.now() - timedelta(days=30))
        with c3: end_date = st.date_input("📅 По", datetime.now())

        df_filtered = get_filtered_data(df, category, start_date, end_date)
        if not df_filtered.empty:
            df_filtered["radius"] = (df_filtered["amount"] / df_filtered["amount"].max()) * 500 if df_filtered["amount"].max() > 0 else 300
            layer = pdk.Layer("ScatterplotLayer", data=df_filtered, get_position='[lon, lat]', get_radius="radius", get_fill_color=[0, 40, 130, 180], pickable=True)
            st.pydeck_chart(pdk.Deck(map_style='light', initial_view_state=pdk.ViewState(latitude=59.9343, longitude=30.3351, zoom=11), layers=[layer], tooltip={"html": "<b>{shop}</b><br>{category}<br>{amount} ₽"}))
            st.dataframe(df_filtered[['date', 'shop', 'category', 'amount']].sort_values('date', ascending=False), use_container_width=True, hide_index=True)
        else: st.info("🙁 Нет данных за выбранный период")

    elif tab == "🎁 Выгода рядом":
        st.markdown("## 🎁 Выгодные предложения партнёров")
        active = [o for o in partners if get_offer_status(o['valid_until'])[0] != 'expired']
        
        # 5. Бэджи "Любимое место" и "Что-то новенькое"
        for offer in active:
            is_fav = offer['shop'] in shops_in_history
            tag = '<span class="badge badge-fav">❤️ Любимое место</span>' if is_fav else ''
            st.markdown(f"""
            <div class="card">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <b>🏬 {offer['shop']}</b> <div>{tag} <span class="badge badge-discount">-{offer['discount_percent']}%</span></div>
                </div>
                <div style="margin-top:8px;">{offer['offer_description']}</div>
                <small style="color:#888;">{offer['address']} | До: {offer['valid_until']}</small>
            </div>
            """, unsafe_allow_html=True)

        # Динамические "Что-то новенькое" (берём категории из истории или статично)
        fav_cats = df['category'].value_counts().head(2).index.tolist() if not df.empty else ['Кафе', 'Продукты']
        st.markdown("### 🌱 Что-то новенькое для вас")
        for i, cat in enumerate(fav_cats[:2]):
            st.markdown(f"""
            <div class="card offer-active">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <b>🛍 Партнёр в категории "{cat}"</b> <span class="badge badge-new">✨ Новинка</span>
                </div>
                <div style="margin-top:5px;">Персональная скидка 10% на первый заказ в новых местах, похожих на ваши траты.</div>
            </div>
            """, unsafe_allow_html=True)

    elif tab == "🔔 Уведомления":
        st.markdown("## 🔔 Уведомления")
        for icon, text, type_ in [
            ("💰", "Экономия на обедах с доставкой уже доступна", "active"),
            ("🎉", "Кешбэк до 10% в Motherbear активен", "active"),
            ("⚠️", "Не упустите предложения в разделе Выгода", "warning")
        ]:
            if type_ == "warning": st.warning(f"{icon} {text}")
            else: st.markdown(f'<div class="card">{icon} {text}</div>', unsafe_allow_html=True)

# ─── БИЗНЕС ИНТЕРФЕЙС ───
elif st.session_state.user_type == 'business':
    apply_business_styles()
    summary = get_business_summary()
    with st.sidebar:
        st.markdown(f'☕ {summary["business_name"]}<br>⭐ {summary["rating"]} ({summary["total_reviews"]} отзывов)', unsafe_allow_html=True)
        st.markdown("---")
        menu = st.radio("Меню", ["📊 Дашборд", "🛠 Создание предложений", "📋 Мои предложения", "⭐ Отзывы"], label_visibility="collapsed")
        st.markdown("---")
        st.caption(datetime.now().strftime('%d.%m.%Y %H:%M'))
        if st.button("🚪 Выйти", use_container_width=True): logout()

    if menu == "📊 Дашборд":
        st.markdown('<div class="header-gradient"><h2 style="margin:0;">Панель управления</h2><p style="margin:5px 0 0 0;">Обзор показателей за 30 дней</p></div>', unsafe_allow_html=True)
        
        # 2. Явная выгода от сотрудничества
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(f'<div class="metric-card"><div class="metric-label">Новых клиентов</div><div class="metric-value">{summary["new_clients"]:,}</div><div class="metric-trend">↑ 23%</div><div class="metric-sub">из ВТБ экосистемы</div></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="metric-card"><div class="metric-label">Выручка</div><div class="metric-value">₽{int(summary["revenue"]):,}</div><div class="metric-trend">↑ 15%</div></div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="metric-card"><div class="metric-label">Транзакций</div><div class="metric-value">{summary["transactions"]:,}</div><div class="metric-trend">↑ 12%</div></div>', unsafe_allow_html=True)
        with c4: st.markdown(f'<div class="metric-card"><div class="metric-label">Ср. чек</div><div class="metric-value">₽{summary["avg_check"]}</div><div class="metric-trend">↑ 5%</div></div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 📈 Выгода от сотрудничества с банком")
        col_a, col_b = st.columns(2)
        with col_a:
            st.info("📊 **ROI рекламного бюджета:** `340%`\nКаждый вложенный в кешбэк рубль вернул 3.40₽ выручки.")
            st.success("🎯 **Конверсия из просмотров в покупки:** `18.4%`\nВыше рынка на 4.2 п.п. благодаря таргетингу ВТБ.")
        with col_b:
            st.metric("💵 Экономия на маркетинге", "₽ 124 500 / мес", "vs реклама в агрегаторах")
            st.metric("🤝 Лояльность клиентов", "+27% повторных визитов", "за 30 дней")

        # Графики
        c_ch1, c_ch2 = st.columns(2)
        with c_ch1:
            metrics = _load_csv('business_metrics.csv')
            if not metrics.empty:
                metrics['date'] = pd.to_datetime(metrics['date'])
                st.line_chart(metrics.set_index('date')['revenue'])
        with c_ch2:
            if not metrics.empty:
                st.bar_chart(metrics.set_index('date')[['new_clients', 'repeat_clients']])

    # 1. Создание/Редактирование предложений
    elif menu == "🛠 Создание предложений":
        st.markdown('<div class="header-gradient"><h2 style="margin:0;">Создание предложения</h2></div>', unsafe_allow_html=True)
        with st.form("new_offer_form"):
            title = st.text_input("Название акции")
            desc = st.text_area("Описание условий")
            col1, col2, col3 = st.columns(3)
            with col1: discount = st.number_input("Скидка (%)", min_value=1, max_value=50, value=10)
            with col2: cat = st.selectbox("Категория", ["Кофе", "Еда", "Топливо", "Розница"])
            with col3: valid_days = st.number_input("Действует (дней)", min_value=1, max_value=90, value=30)
            
            submitted = st.form_submit_button("🚀 Опубликовать")
            if submitted:
                valid_until = (datetime.now() + timedelta(days=valid_days)).strftime('%Y-%m-%d')
                new_offer = {
                    'id': len(st.session_state.session_offers) + 1,
                    'title': title, 'description': desc, 'discount_percent': discount,
                    'valid_from': datetime.now().strftime('%Y-%m-%d'), 'valid_until': valid_until,
                    'category': cat, 'min_purchase_amount': 0, 'is_active': True
                }
                st.session_state.session_offers.append(new_offer)
                st.success("✅ Предложение успешно создано! Оно появится у клиентов в разделе «Выгода рядом».")
        
        # Предпросмотр результатов
        if st.session_state.session_offers:
            st.markdown("### 📊 Прогноз эффективности по созданным акциям")
            df_offers = pd.DataFrame(st.session_state.session_offers)
            df_offers['Привлечено клиентов'] = [int(d*1.5) for d in df_offers['discount_percent']]
            df_offers['Ожидаемый оборот'] = df_offers['Привлечено клиентов'] * 500
            st.dataframe(df_offers, use_container_width=True)

    elif menu == "📋 Мои предложения":
        offers = load_business_offers() + st.session_state.session_offers
        for o in offers:
            st.markdown(f'<div class="offer-card"><div style="display:flex;justify-content:space-between;"><h3 style="margin:0;">{o["title"]}</h3><span class="offer-badge">-{o["discount_percent"]}%</span></div><p>{o.get("description","")}</p></div>', unsafe_allow_html=True)
            
    elif menu == "⭐ Отзывы":
        st.markdown("### ⭐ Отзывы клиентов")
        reviews = _load_csv('business_reviews.csv')
        if not reviews.empty:
            for _, r in reviews.head(10).iterrows():
                stars = "⭐ " * int(r['rating']) + "☆ " * (5 - int(r['rating']))
                st.markdown(f'<div class="review-card">{stars} <b>{r["client_name"]}</b><br>{r["comment"]}</div>', unsafe_allow_html=True)
