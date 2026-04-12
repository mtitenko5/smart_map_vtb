import streamlit as st

def apply_styles():
    st.markdown("""
    <style>
    /* 6. Принудительная светлая тема (переопределение системной тёмной) */
    :root {
        --background-color: #ffffff !important;
        --text-color: #0e1117 !important;
        --secondary-background-color: #f8f9fa !important;
    }
    .stApp, .main, .stApp > div {
        background: linear-gradient(180deg, #dfefff, #f6faff) !important;
        color: #0e1117 !important;
    }
    /* Скрытие стандартных заголовков и переключателей темы */
    header, footer { visibility: hidden !important; }
    .st-emotion-cache-18ni7ap { background: transparent !important; }

    .card {
        background: rgba(255,255,255,0.85);
        padding: 15px;
        border-radius: 20px;
        box-shadow: 0 4px 20px rgba(0,0,0, 0.05);
        margin-bottom: 10px;
        color: #1a1a1a;
    }
    .big-card { padding: 20px; border-radius: 24px; }
    
    button {
        border-radius: 20px !important;
        background: linear-gradient(90deg, #5aa9ff, #7fc8ff) !important;
        color: white !important;
        border: none !important;
    }
    .offer-active { background: rgba(200, 255, 220, 0.8); border-left: 4px solid #28a745; }
    .offer-expiring { background: rgba(255, 243, 205, 0.8); border-left: 4px solid #ffc107; }
    .offer-expired { background: rgba(248, 215, 218, 0.8); border-left: 4px solid #dc3545; opacity: 0.6; }
    
    .login-container {
        max-width: 420px; margin: 40px auto; padding: 30px;
        border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        background-color: rgba(255,255,255,0.95); text-align: center; color: #333;
    }
    .vtb-title { color: #002882; font-family: 'Arial', sans-serif; font-size: 26px; font-weight: bold; margin-bottom: 8px; }
    .ux-text { font-size: 14px; color: #555; margin-bottom: 20px; line-height: 1.6; }
    
    .badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold; margin-left: 8px; }
    .badge-discount { background: linear-gradient(90deg, #5aa9ff, #7fc8ff); color: white; }
    .badge-fav { background: linear-gradient(90deg, #4facfe, #00f2fe); color: white; }
    .badge-new { background: linear-gradient(90deg, #43e97b, #38f9d7); color: #064e3b; }
    
    .stRadio > label { font-size: 16px; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

def apply_business_styles():
    st.markdown("""
    <style>
    :root { --background-color: #ffffff !important; --text-color: #0e1117 !important; }
    .stApp, .main, .stApp > div { background: linear-gradient(180deg, #e8f4ff, #f0f8ff) !important; color: #0e1117 !important; }
    header, footer { visibility: hidden !important; }

    .card { background: rgba(255,255,255,0.85); padding: 15px; border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0, 0.05); margin-bottom: 10px; color: #333; }
    .big-card { padding: 20px; border-radius: 24px; background: rgba(255,255,255,0.8); }
    .metric-card { background: rgba(255,255,255,0.9); padding: 20px; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,40,130,0.1); text-align: center; color: #333; }
    .metric-value { font-size: 32px; font-weight: bold; color: #002882; margin: 10px 0; }
    .metric-label { color: #666; font-size: 14px; }
    .metric-trend { color: #28a745; font-size: 13px; font-weight: 600; margin-top: 5px; }
    .metric-sub { color: #888; font-size: 12px; margin-top: 5px; }
    
    button { border-radius: 20px !important; background: linear-gradient(90deg, #5aa9ff, #7fc8ff) !important; color: white !important; border: none !important; }
    .offer-card { background: rgba(255,255,255,0.85); padding: 20px; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.08); margin-bottom: 15px; border-left: 5px solid #28a745; color: #333; }
    .offer-badge { background: linear-gradient(90deg, #5aa9ff, #7fc8ff); color: white; padding: 5px 15px; border-radius: 20px; font-weight: bold; font-size: 14px; }
    .review-card { background: rgba(255,255,255,0.7); padding: 15px; border-radius: 15px; margin-bottom: 10px; border-left: 3px solid #5aa9ff; color: #333; }
    .star-rating { color: #ffc107; font-size: 18px; }
    
    .login-container { max-width: 450px; margin: 40px auto; padding: 30px; border-radius: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); background-color: rgba(255,255,255,0.95); text-align: center; color: #333; }
    .vtb-title { color: #002882; font-family: 'Arial', sans-serif; font-size: 26px; font-weight: bold; margin-bottom: 8px; }
    .ux-text { font-size: 14px; color: #555; margin-bottom: 20px; line-height: 1.6; }
    .header-gradient { background: linear-gradient(90deg, #002882, #0055b8); color: white; padding: 25px; border-radius: 20px; margin-bottom: 25px; }
    .stRadio > label { font-size: 16px; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)
