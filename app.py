import streamlit as st
import yfinance as yf
import google.generativeai as genai
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import concurrent.futures
from gtts import gTTS
import io

# ==========================================
# 🔑 設定
# ==========================================
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("鍵（Secrets）が設定されていません。")
    st.stop()

MODEL_NAME = "gemini-2.5-flash"

st.set_page_config(page_title="トレーダーズ・ステーション Pro", layout="wide")

if "scan_results" not in st.session_state:
    st.session_state.scan_results = None

# ==========================================
# 🧠 関数群
# ==========================================
def calculate_lines(df, window=20):
    df['Resistance'] = df['High'].rolling(window=window).max()
    df['Support'] = df['Low'].rolling(window=window).min()
    x = np.arange(len(df))
    y = (df['High'].values + df['Low'].values) / 2
    slope, intercept = np.polyfit(x, y, 1)
    df['Trend_Slope'] = slope
    df['Trend_Center'] = slope * x + intercept
    std_dev = np.std(y - df['Trend_Center'])
    df['Trend_Upper'] = df['Trend_Center'] + (2 * std_dev)
    df['Trend_Lower'] = df['Trend_Center'] - (2 * std_dev)
    return df

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def fetch_and_analyze(item):
    name, code = item
    if code == "": return None
    try:
        stock_data = yf.Ticker(code).history(period="3mo")
        if stock_data.empty: return None
        current_price = stock_data['Close'].iloc[-1]
        rsi_series = calculate_rsi(stock_data['Close'])
        current_rsi = rsi_series.iloc[-1]
        x = np.arange(len(stock_data))
        slope, _ = np.polyfit(x, stock_data['Close'], 1)
        return {
            "コード": code,
            "銘柄名": name,
            "現在値": f"{current_price:,.2f}",
            "RSI": f"{current_rsi:.1f}",
            "判定コメント": ("上昇" if slope > 0 else "") + (", RSI安" if current_rsi <= 30 else ""),
            "raw_rsi": current_rsi,
            "raw_slope": slope
        }
    except:
        return None

# 🗣️ 音声再生関数 (自動再生ON)
def play_text_to_speech(text):
    try:
        clean_text = text.replace("*", "").replace("#", "").replace(":", "、").replace("\n", "。")
        tts = gTTS(text=clean_text, lang='ja')
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        st.audio(audio_bytes, format='audio/mp3', autoplay=True)
    except Exception as e:
        st.warning(f"読み上げエラー: {e}")

# ==========================================
# 📱 画面表示
# ==========================================
st.subheader("📊 トレーダーズ・ステーション Pro (Auto Voice 🗣️)")

with st.sidebar:
    st.header("🔍 爆速スキャナー")
    use_rsi = st.checkbox("RSIで絞り込む", value=True)
    rsi_threshold = st.slider("RSIがこれ以下", 10, 50, 30)
    use_trend = st.checkbox("上昇トレンドのみ", value=False)
    if st.button("スキャン開始 🚀", type="primary"):
        st.session_state.run_scan = True

area = st.radio("エリア選択", ["🇯🇵 日本", "🇺🇸 米国", "🌏 世界・資源", "💱 FX"], horizontal=True)

meigara_list = {}
if area == "🇯🇵 日本":
    cat = st.radio("カテゴリー", ["📋 主要", "💰 値がさ", "👛 手頃", "📉 低位・ボロ株", "💎 掘出し物"], horizontal=True)
    if cat == "📋 主要": meigara_list = {"🔍 手動": "", "🇯🇵 日経平均": "^N225", "🇯🇵 トヨタ": "7203.T", "🇯🇵 UFJ": "8306.T", "🇯🇵 ソニーG": "6758.T", "🇯🇵 SBG": "9984.T"}
    elif cat == "💰 値がさ": meigara_list = {"🔍 手動": "", "🇯🇵 ファストリ": "9983.T", "🇯🇵 東エレク": "8035.T", "🇯🇵 キーエンス": "6861.T", "🇯🇵 任天堂": "7974.T"}
    elif cat == "👛 手頃": meigara_list = {"🔍 手動": "", "🇯🇵 ENEOS": "5020.T", "🇯🇵 楽天G": "4755.T", "🇯🇵 イオン": "8267.T", "🇯🇵 ホンダ": "7267.T"}
    elif cat == "📉 低位・ボロ株": meigara_list = {"🔍 手動": "", "🇯🇵 日産": "7201.T", "🇯🇵 セブン銀": "8410.T", "🇯🇵 LY": "4689.T", "🇯🇵 マツダ": "7261.T", "🇯🇵 NTN": "6472.T"}
    else: meigara_list = {"🔍 手動": "", "🇯🇵 レーザー": "6920.T", "🇯🇵 メルカリ": "4385.T", "🇯🇵 カバー": "5253.T", "🇯🇵 QPS": "5595.T", "🇯🇵 さくら": "3778.T"}
elif area == "🇺🇸 米国":
    cat = st.radio("カテゴリー", ["📋 指数", "🚀 M7", "🛡️ 高配当", "💎 成長"], horizontal=True)
    if cat == "📋 指数": meigara_list = {"🔍 手動": "", "🇺🇸 S&P500": "SPY", "🇺🇸 QQQ": "QQQ", "🇺🇸 ダウ": "DIA"}
    elif cat == "🚀 M7": meigara_list = {"🔍 手動": "", "🇺🇸 NVDA": "NVDA", "🇺🇸 AAPL": "AAPL", "🇺🇸 MSFT": "MSFT", "🇺🇸 AMZN": "AMZN", "🇺🇸 TSLA": "TSLA"}
    elif cat == "🛡️ 高配当": meigara_list = {"🔍 手動": "", "🇺🇸 KO": "KO", "🇺🇸 PG": "PG", "🇺🇸 JNJ": "JNJ"}
    else: meigara_list = {"🔍 手動": "", "🇺🇸 PLTR": "PLTR", "🇺🇸 COIN": "COIN", "🇺🇸 ARM": "ARM"}
elif area == "🌏 世界・資源":
    meigara_list = {"🔍 手動": "", "🥇 金": "GLD", "🛢 原油": "CL=F", "🪙 BTC": "BTC-USD", "🇮🇳 印SENSEX": "^BSESN"}
else: 
    cat = st.radio("カテゴリー", ["🇯🇵 クロス円", "🌎 ドルスト"], horizontal=True)
    if cat == "🇯🇵 クロス円": meigara_list = {"🔍 手動": "", "🇺🇸/🇯🇵 ドル円": "USDJPY=X", "🇪🇺/🇯🇵 ユーロ円": "EURJPY=X", "🇬🇧/🇯🇵 ポンド円": "GBPJPY=X"}
    else: meigara_list = {"🔍 手動": "", "🇪🇺/🇺🇸 ユーロドル": "EURUSD=X", "🇬🇧/🇺🇸 ポンドドル": "GBPUSD=X"}

if st.session_state.get("run_scan", False):
    target_items = list(meigara_list.items())
    hit_data = []
    with st.spinner(f"🚀 全力スキャン中... ({len(target_items)-1}件)"):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = list(executor.map(fetch_and_analyze, target_items))
        for res in results:
            if res is None: continue
            is_hit = True
            if use_rsi and res['raw_rsi'] > rsi_threshold: is_hit = False
            if use_trend and res['raw_slope'] <= 0: is_hit = False
            if is_hit: hit_data.append(res)
    
    if hit_data:
        st.session_state.scan_results = pd.DataFrame(hit_data).drop(columns=['raw_rsi', 'raw_slope'])
        st.success(f"💎 {len(hit_data)}件ヒット！ 表をクリック 👇")
    else:
        st.session_state.scan_results = pd.DataFrame()
        st.warning("条件に合う銘柄なし")
    st.session_state.run_scan = False

selected_ticker_from_table = None
if st.session_state.scan_results is not None and not st.session_state.scan_results.empty:
    event = st.dataframe(st.session_state.scan_results, selection_mode="single-row", on_select="rerun", hide_index=True, use_container_width=True, key="scan_table")
    if len(event.selection.rows) > 0:
        idx = event.selection.rows[0]
        selected_ticker_from_table = st.session_state.scan_results.iloc[idx]["コード"]

st.markdown("---")
target_ticker = ""
auto_run = False
if selected_ticker_from_table:
    target_ticker = selected_ticker_from_table
    st.info(f"👆 選択中: **{target_ticker}**")
    auto_run = True
else:
    col1, col2 = st.columns([2, 1])
    with col1:
        opt = st.selectbox("銘柄リスト", list(meigara_list.keys()))
        target_ticker = st.text_input("コード入力") if opt == "🔍 手動" else meigara_list.get(opt, "")
    with col2:
        period = st.selectbox("期間", ["1mo", "3mo", "6mo", "1y"], index=2)

if auto_run or st.button("AI詳細分析開始 🚀", use_container_width=True):
    if not target_ticker: st.warning("銘柄を選んでください"); st.stop()
    if 'period' not in locals(): period = "6mo"

    with st.spinner(f"{target_ticker} を徹底分析 & レポート作成中..."):
        try:
            stock = yf.Ticker(target_ticker)
            df = stock.history(period=period)
            if df.empty: st.error("データ取得不可")
            else:
                df = calculate_lines(df)
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='価格'))
                fig.add_trace(go.Scatter(x=df.index, y=df['Resistance'], mode='lines', line=dict(color='rgba(255, 165, 0, 0.6)', dash='dot'), name='上値抵抗'))
                fig.add_trace(go.Scatter(x=df.index, y=df['Support'], mode='lines', line=dict(color='rgba(50, 205, 50, 0.6)', dash='dot'), name='下値支持'))
                slope = df['Trend_Slope'].iloc[-1]
                color = 'rgba(255, 80, 80, 0.9)' if slope > 0 else 'rgba(80, 80, 255, 0.9)'
                fig.add_trace(go.Scatter(x=df.index, y=df['Trend_Upper'], mode='lines', line=dict(color=color), name='上限'))
                fig.add_trace(go.Scatter(x=df.index, y=df['Trend_Center'], mode='lines', line=dict(color=color, dash='dash'), name='中心'))
                fig.add_trace(go.Scatter(x=df.index, y=df['Trend_Lower'], mode='lines', line=dict(color=color), showlegend=False))
                
                fig.update_layout(title=f"{target_ticker} 自動解析チャート", height=500, xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)

                current_price = df['Close'].iloc[-1]
                change = ((current_price - df['Close'].iloc[0]) / df['Close'].iloc[0]) * 100
                rsi_val = calculate_rsi(df['Close']).iloc[-1]
                
                prompt = f"""
                あなたはプロの投資家です。{target_ticker}を分析してください。
                価格: {current_price:.2f}, 変動: {change:.2f}%, RSI: {rsi_val:.2f}, トレンド: {'上昇' if slope > 0 else '下降'}
                【構成】
                1. トレンド診断
                2. 需給と節目
                3. 売買戦略
                """
                genai.configure(api_key=API_KEY)
                model = genai.GenerativeModel(MODEL_NAME)
                response = model.generate_content(prompt)
                
                st.info("📊 AI分析レポート")
                st.markdown(response.text)

                st.markdown("---")
                st.markdown("### 🗣️ 解説を聞く")
                play_text_to_speech(response.text)

        except Exception as e:
            st.error(f"エラー: {e}")