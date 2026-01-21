import streamlit as st
import google.generativeai as genai
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd
from datetime import datetime

# --- 設定 ---
MODEL_NAME = "gemini-flash-latest"

st.set_page_config(page_title="トレードAI分析 Master", layout="wide")
st.title("💹 トレードAI分析 Master")

# --- サイドバー設定 ---
with st.sidebar:
    st.header("⚙️ 設定")
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except:
        api_key = st.text_input("Gemini APIキー", type="password")

    if api_key:
        genai.configure(api_key=api_key)

# --- 共通関数: データ取得 & テクニカル計算 ---
def get_data_and_tech(ticker, days=180):
    try:
        df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False)
        if df.empty:
            return None
        
        # テクニカル計算
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['SMA50'] = df['Close'].rolling(window=50).mean()
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        return df
    except:
        return None

# --- AIプロンプト ---
PROMPT_SINGLE = """
あなたはプロのトレーダーです。以下のデータから「トレンド」「売買判断（買い/売り/様子見）」「戦略」を簡潔に分析してください。
FXの場合は売り目線も重要視してください。
"""

PROMPT_SCAN = """
あなたはスカウトマンです。この銘柄が「今の瞬間に」買いか売りか、一言でズバリ判定してください。
チャンスでなければ「対象外」と答えてください。
"""

# === タブで機能を切り替え ===
tab1, tab2 = st.tabs(["📈 個別診断 (FX/株)", "💎 お宝発掘スキャン"])

# ==========================================
# タブ1: 個別診断 (さっきの機能)
# ==========================================
with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        ticker = st.text_input("銘柄コード (例: 7203.T, USDJPY=X)", value="USDJPY=X", key="t1_ticker")
    with col2:
        days = st.slider("期間", 30, 365, 180, key="t1_days")
    
    if st.button("AI分析を開始", key="btn_single"):
        if not api_key:
            st.error("APIキーが設定されていません")
        else:
            with st.spinner("分析中..."):
                df = get_data_and_tech(ticker, days)
                if df is not None:
                    # チャート表示
                    fig = go.Figure()
                    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='ローソク'))
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], line=dict(color='orange'), name='SMA20'))
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], line=dict(color='blue'), name='SMA50'))
                    fig.update_layout(height=500, title=f"{ticker} チャート")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # AI分析
                    st.subheader("🤖 Gemini先生の診断")
                    model = genai.GenerativeModel(MODEL_NAME)
                    last_data = df.iloc[-1]
                    info = f"銘柄:{ticker} 終値:{last_data['Close']:.2f} RSI:{last_data['RSI']:.2f}"
                    res = model.generate_content(f"{PROMPT_SINGLE}\n{info}")
                    st.markdown(res.text)
                else:
                    st.error("データが見つかりません。コードを確認してください（日本株は .T が必要）")

# ==========================================
# タブ2: お宝発掘スキャン (復活させた機能)
# ==========================================
with tab2:
    st.markdown("##### 複数の銘柄を一気にチェックします！")
    
    # スキャン対象リスト（自由に変えてください）
    default_tickers = "7203.T, 9984.T, 8306.T, 6758.T, 6920.T, USDJPY=X, EURUSD=X"
    target_tickers = st.text_area("リスト (カンマ区切り)", value=default_tickers)
    
    # 条件設定
    rsi_threshold = st.slider("RSIがこれ以下なら「売られすぎ」と判定", 20, 50, 30)
    
    if st.button("お宝スキャン開始", key="btn_scan"):
        if not api_key:
            st.error("APIキーが必要です")
        else:
            ticker_list = [t.strip() for t in target_tickers.split(',')]
            st.write(f"{len(ticker_list)} 銘柄をスキャン中... (時間がかかります)")
            
            model = genai.GenerativeModel(MODEL_NAME)
            
            for t in ticker_list:
                with st.container():
                    df = get_data_and_tech(t, 100)
                    if df is not None:
                        last_rsi = df['RSI'].iloc[-1]
                        last_price = df['Close'].iloc[-1]
                        
                        # 条件: RSIが低い、または AIに見せたい場合
                        if last_rsi <= rsi_threshold:
                            st.markdown(f"**🔥 発見: {t}** (RSI: {last_rsi:.1f})")
                            
                            # 小さなチャート表示
                            st.line_chart(df['Close'])
                            
                            # AIの一言コメント
                            info = f"銘柄:{t} 終値:{last_price} RSI:{last_rsi}"
                            res = model.generate_content(f"{PROMPT_SCAN}\n{info}")
                            st.info(res.text)
                            st.divider()
            
            st.success("スキャン完了！")