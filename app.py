import streamlit as st
import google.generativeai as genai
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd

# --- 設定 ---
# 制限が緩く、動作が確実なモデル
MODEL_NAME = "gemini-flash-latest"

# AIへの指示（ここはFX対応のままにしています）
PROMPT = """
あなたはプロのトレーダーです。
提供されたチャートとRSIを見て、以下の点を日本語で簡潔に分析してください。

1. **トレンド**: 上昇・下降・レンジ
2. **売買判断**:
   - 【買い (LONG)】: 上昇の押し目、底値圏
   - 【売り (SHORT)】: 下降の戻り目、天井圏（FXでは特に重要）
   - 【様子見 (WAIT)】
3. **戦略**: エントリーと損切りの目安

※FXや暗号資産の場合は「売り（ショート）」のチャンスも積極的に指摘してください。
"""

st.set_page_config(page_title="Simple Trade AI", layout="wide")
st.title("📈 シンプル・トレード分析")

# --- サイドバー（入力欄のみ） ---
with st.sidebar:
    st.header("設定")
    
    # APIキー
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except:
        api_key = st.text_input("Gemini APIキー", type="password")
    
    # シンプルな入力欄（ここに好きなコードを入れるだけ）
    ticker = st.text_input("銘柄コード", value="USDJPY=X")
    
    # 忘れたとき用のメモ（機能には影響しません）
    st.caption("""
    【入力のヒント】
    - 🇯🇵 日本株 : 7203.T (数字 + .T)
    - 🇺🇸 米国株 : NVDA, TSLA
    - 🌎 F X : USDJPY=X, EURUSD=X
    - ₿ 仮想通貨: BTC-USD
    """)
    
    days = st.slider("期間 (日)", 30, 365, 180)
    
    btn = st.button("分析する", type="primary")

# --- メイン処理 ---
if btn and api_key:
    genai.configure(api_key=api_key)
    
    with st.spinner(f"{ticker} を取得中..."):
        try:
            # データ取得
            df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False)
            
            if df.empty:
                st.error("データが見つかりません。コードを確認してください（日本株は .T が必要です）")
            else:
                # テクニカル計算
                df['SMA20'] = df['Close'].rolling(window=20).mean()
                df['SMA50'] = df['Close'].rolling(window=50).mean()
                
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                df['RSI'] = 100 - (100 / (1 + rs))

                # チャート表示
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='ローソク'))
                fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], line=dict(color='orange'), name='SMA20'))
                fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], line=dict(color='blue'), name='SMA50'))
                fig.update_layout(height=600, title=f"{ticker} チャート")
                st.plotly_chart(fig, use_container_width=True)

                # AI診断
                st.subheader("🤖 AI分析レポート")
                model = genai.GenerativeModel(MODEL_NAME)
                
                last_price = df['Close'].iloc[-1]
                last_rsi = df['RSI'].iloc[-1]
                
                info = f"銘柄: {ticker}\n現在値: {last_price:.2f}\nRSI(14): {last_rsi:.2f}"
                response = model.generate_content(f"{PROMPT}\n\n【データ】\n{info}")
                
                st.markdown(response.text)

        except Exception as e:
            st.error(f"エラー: {e}")