import streamlit as st
import yfinance as yf
import requests
import json
from bs4 import BeautifulSoup
import urllib.parse
import pandas as pd

# ==========================================
# 🔑 設定
# ==========================================
API_KEY = st.secrets["GEMINI_API_KEY"]
MODEL_NAME = "gemini-2.5-flash"

st.set_page_config(page_title="Gemini Trader Station", layout="wide")
st.title(f"🤖 Gemini トレーダーズ・ステーション")

# --- 📦 セッション管理 ---
if 'selected_stock' not in st.session_state:
    st.session_state['selected_stock'] = None

# デフォルトの注目株
DEFAULT_CUSTOM_LIST = "4825, 8563, 6337, 4967, 3994, 5253, 3231, 3665, 5981"

# 📜 固定リスト
WATCHLIST_MAJOR = ["7203.T", "9984.T", "8306.T", "6758.T", "6861.T", "7974.T", "8035.T", "6501.T", "9432.T", "6146.T", "1570.T"]
WATCHLIST_LOW = ["4755.T", "5020.T", "7211.T", "9501.T", "8604.T", "6178.T", "3861.T", "3402.T", "5406.T", "8316.T"]
WATCHLIST_ULTRA = ["9432.T", "4689.T", "7201.T", "4005.T", "8410.T", "6740.T", "3401.T", "2353.T", "8524.T", "5202.T"]

# 🕵️‍♂️ 掘り出し物候補（監視対象：怪しい動きをしがちな中小型株・仕手系）
# ここから「サインが出たやつ」だけを表示します
WATCHLIST_HIDDEN_GEMS = [
    "2127.T", "2150.T", "2160.T", "2315.T", "2337.T", "2370.T", "2929.T", "3031.T", 
    "3048.T", "3103.T", "3133.T", "3323.T", "3624.T", "3667.T", "3778.T", "3807.T",
    "3825.T", "3903.T", "3911.T", "3936.T", "4080.T", "4344.T", "4425.T", "4563.T",
    "4583.T", "4591.T", "4594.T", "4714.T", "4777.T", "4880.T", "5032.T", "5246.T",
    "5726.T", "6047.T", "6176.T", "6182.T", "6255.T", "6573.T", "6619.T", "6627.T",
    "6890.T", "6966.T", "7003.T", "7014.T", "7071.T", "7238.T", "7342.T", "7776.T"
]

# --- 🛠️ 関数群 ---

def get_stock_news(stock_name):
    query = urllib.parse.quote(f"{stock_name} 株価 ニュース")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        response = requests.get(rss_url, timeout=5)
        soup = BeautifulSoup(response.content, features="xml")
        items = soup.findAll('item')[:3]
        news_text = ""
        for item in items:
            title = item.title.text
            pub_date = item.pubDate.text
            news_text += f"- {title} ({pub_date})\n"
        return news_text if news_text else "（特になし）"
    except:
        return "（取得失敗）"

def ask_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"エラー: {response.text}"
    except Exception as e:
        return f"通信エラー: {e}"

@st.cache_data(ttl=3600)
def scan_stocks(target_list, filter_mode=None):
    data_list = []
    for code in target_list:
        code = code.strip().replace(" ", "").replace("　", "")
        if not code: continue
        if code.isdigit(): code = code + ".T"
            
        try:
            stock = yf.Ticker(code)
            # 長めのデータを取ってトレンド判定
            hist = stock.history(period="3mo")
            
            if not hist.empty and len(hist) >= 26:
                current = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2]
                pct = ((current - prev) / prev) * 100
                
                # テクニカル指標計算
                ma5 = hist['Close'].rolling(window=5).mean().iloc[-1]
                ma25 = hist['Close'].rolling(window=25).mean().iloc[-1]
                volume_mean = hist['Volume'].iloc[-5:].mean()
                current_volume = hist['Volume'].iloc[-1]
                
                info = stock.info
                name = info.get('longName', code).replace("株式会社", "").replace("（株）", "")

                # 🕵️‍♂️ 掘り出し物フィルター
                status = ""
                is_gem = False
                
                if filter_mode == "gems":
                    # 条件1: ゴールデンクロス（短期線が長期線を抜いた）
                    # 条件2: 出来高急増（平均の2倍以上）
                    # 条件3: 5%以上の急騰
                    if ma5 > ma25 and hist['Close'].iloc[-2] < hist['Close'].rolling(window=25).mean().iloc[-2]:
                         status = "✨GC発生"
                         is_gem = True
                    elif current_volume > volume_mean * 2.5:
                         status = "💥出来高急増"
                         is_gem = True
                    elif pct > 4.0:
                         status = "🚀急騰中"
                         is_gem = True
                    
                    if is_gem:
                         data_list.append({"code": code, "name": name, "price": current, "pct": pct, "status": status})
                else:
                    # 通常モード
                    data_list.append({"code": code, "name": name, "price": current, "pct": pct, "status": ""})

        except:
            pass
    return pd.DataFrame(data_list)

def render_stock_list(df, key_suffix, max_price=None):
    if df.empty:
        if key_suffix == "gems":
            st.info("現在、サインが出ている掘り出し物はありません。")
        else:
            st.info("データなし")
        return
    if max_price:
        df = df[df['price'] <= max_price]
    df = df.sort_values(by="pct", ascending=False)

    for index, row in df.iterrows():
        # アイコン設定（掘り出し物は特別仕様）
        if row['status']:
            label = f"🚨 {row['status']} | {row['name']} ({row['pct']:+.2f}%)"
        else:
            icon = "🔥" if row['pct'] > 2.0 else "🚀" if row['pct'] > 0 else "☔" if row['pct'] < -2.0 else "☁️"
            label = f"{icon} {row['name']} | {row['price']:,.0f}円 ({row['pct']:+.2f}%)"
            
        unique_key = f"btn_{row['code']}_{key_suffix}"
        if st.button(label, key=unique_key, use_container_width=True):
            st.session_state['selected_stock'] = row['code']

# ==========================================
# 🖥️ 画面レイアウト
# ==========================================

with st.sidebar:
    st.header("📝 監視リスト設定")
    st.caption("カンマ区切りで入力")
    user_input_codes = st.text_area("自由入力欄", value=DEFAULT_CUSTOM_LIST, height=100)
    if user_input_codes:
        custom_watchlist = user_input_codes.split(",")
    else:
        custom_watchlist = []

col_radar, col_detail = st.columns([1, 2])

# --- 👈 左：市場レーダー ---
with col_radar:
    st.subheader("📡 市場スキャナー")
    if st.button("🔄 更新", use_container_width=True):
        scan_stocks.clear()
        st.rerun()

    # タブ5つめ「🕵️‍♂️ 掘出し物」を追加！
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📝 自由", "🏆 主要", "💎 1000", "🪙 500", "🕵️‍♂️ 掘出"])
    
    with tab1:
        st.caption("自由入力リスト")
        if custom_watchlist:
            with st.spinner('スキャン中...'):
                df_custom = scan_stocks(custom_watchlist)
            render_stock_list(df_custom, "custom")
    
    with tab2:
        with st.spinner('スキャン中...'):
            render_stock_list(scan_stocks(WATCHLIST_MAJOR), "major")
            
    with tab3:
        with st.spinner('スキャン中...'):
            render_stock_list(scan_stocks(WATCHLIST_LOW), "low", max_price=1200)
            
    with tab4:
        with st.spinner('スキャン中...'):
            render_stock_list(scan_stocks(WATCHLIST_ULTRA), "ultra", max_price=550)
            
    # ここが新機能！
    with tab5:
        st.caption("サイン点灯中のお宝株")
        st.write("中小型株約50社から、**「急騰・出来高急増・ゴールデンクロス」**が発生した銘柄だけを抽出します。")
        with st.spinner('怪しい動きを捜索中...'):
            df_gems = scan_stocks(WATCHLIST_HIDDEN_GEMS, filter_mode="gems")
        render_stock_list(df_gems, "gems")

# --- 👉 右：詳細分析 ---
with col_detail:
    st.markdown("### 🏥 AI ガチ診断")
    
    search_col1, search_col2 = st.columns([3, 1])
    with search_col1:
        manual_input = st.text_input("🔍 コード検索", placeholder="例: 7203")
    with search_col2:
        st.write("") 
        st.write("") 
        if st.button("検索"):
            if manual_input:
                code_to_set = manual_input + ".T" if manual_input.isdigit() else manual_input
                st.session_state['selected_stock'] = code_to_set

    st.markdown("---")

    if st.session_state['selected_stock']:
        target_code = st.session_state['selected_stock']
        try:
            stock = yf.Ticker(target_code)
            hist = stock.history(period="3mo") # 期間を少し長くしてトレンド見やすく
            info = stock.info
            name = info.get('longName', target_code)
            
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
                st.markdown(f"## 📈 {name} <small>({target_code})</small>", unsafe_allow_html=True)
                st.line_chart(hist['Close'])
                
                with st.spinner(f'{MODEL_NAME} が分析中...'):
                    news = get_stock_news(name)
                    prompt = f"""
                    あなたは冷徹なプロの機関投資家です。
                    対象銘柄: {name} ({target_code})
                    現在値: {current_price}円
                    直近の動き: {hist['Close'].tail(5).to_list()}
                    出来高の変化: {hist['Volume'].tail(5).to_list()}
                    最新ニュース: {news}
                    
                    特に「出来高の急増」や「チャートの初動」に注目して分析してください。
                    
                    ## 判定: 【 買い / 売り / 様子見 】 (どれか一つ断言)
                    ### 💀 辛口トレンド分析
                    ### 🎯 仕込み時・逃げ時の戦略
                    """
                    result = ask_gemini(prompt)
                    with st.expander("🔍 参照ニュース"):
                        st.text(news)
                    st.success("分析完了")
                    st.markdown(result)
            else:
                st.error(f"データが見つかりません: {target_code}")
        except Exception as e:
            st.error(f"エラー: {e}")
    else:
        st.info("👈 左のリストから選ぶか、検索ボックスに入力してください。")