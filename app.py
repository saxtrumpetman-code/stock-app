import streamlit as st
import google.generativeai as genai
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd

# --- 設定 ---
MODEL_NAME = "gemini-flash-latest"

st.set_page_config(page_title="トレードAI分析 Pro", layout="wide")
st.title("📈 トレードAI分析 Pro (スクリーニング付)")

# --- サイドバー (操作メニュー) ---
with st.sidebar:
    st.header("1. 設定")
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except:
        api_key = st.text_input("Gemini APIキー", type="password")

    st.divider()

    # --- ① 個別分析メニュー ---
    st.header("2. 個別銘柄の分析")
    ticker = st.text_input("コード入力 (例: 7203.T)", value="7203.T")
    days = st.slider("期間 (日)", 30, 365, 180)
    
    # メインの実行ボタン
    btn_single = st.button("🚀 チャート分析を実行", type="primary")

    st.divider()

    # --- ② 株式スクリーニングメニュー ---
    st.header("3. 株式スクリーニング")
    st.caption("ボタンを押すとリストをスキャンします")
    
    btn_low = st.button("💰 定位株 (低位株) を見る")
    btn_large = st.button("🏢 主力株 (大型株) を見る")

# --- メイン処理 ---
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)

    # ---------------------------------------------------
    # パターンA：スクリーニングボタンが押された場合
    # ---------------------------------------------------
    if btn_low or btn_large:
        # リストのセット
        if btn_low:
            target_list = ["4755.T", "5020.T", "7201.T", "4689.T", "8410.T"] # 楽天, ENEOS, 日産...
            st.subheader("💰 定位株（低位株）のAI判定")
        else:
            target_list = ["7203.T", "8306.T", "9984.T", "6758.T", "8035.T"] # トヨタ, 三菱UFJ...
            st.subheader("🏢 主力株（大型株）のAI判定")

        # ★ここを修正：一番頑丈なデータ取得方法に変更★
        for t in target_list:
            with st.container(border=True):
                try:
                    # yf.Ticker().history() は単体取得に特化しておりエラーが起きにくい
                    stock = yf.Ticker(t)
                    df = stock.history(period="100d")
                    
                    if df.empty:
                        st.error(f"❌ {t}: データが取れませんでした")
                    else:
                        # 簡易計算
                        last_price = df['Close'].iloc[-1]
                        delta = df['Close'].diff()
                        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                        rs = gain / loss
                        rsi_val = 100 - (100 / (1 + rs))
                        rsi = rsi_val.iloc[-1] # 最新のRSI

                        col_chart, col_text = st.columns([2, 1])
                        
                        # ミニチャート
                        with col_chart:
                            st.markdown(f"**{t}**")
                            st.line_chart(df['Close'], height=150)
                        
                        # AI判定
                        with col_text:
                            st.metric("株価", f"{last_price:.0f} 円", f"RSI: {rsi:.1f}")
                            
                            prompt = f"""
                            株銘柄: {t}
                            現在値: {last_price:.0f}円
                            RSI: {rsi:.1f}
                            
                            質問: 今、買い時ですか？
                            回答: 一言で「買い」「売り」「様子見」と判定し、理由を1行で述べてください。
                            """
                            with st.spinner("AI判定中..."):
                                res = model.generate_content(prompt)
                                st.info(res.text)
                except Exception as e:
                    st.error(f"⚠️ {t}: エラー ({e})")

    # ---------------------------------------------------
    # パターンB：個別分析 (Pro版の画面) ※デフォルト
    # ---------------------------------------------------
    elif btn_single: 
        with st.spinner(f"{ticker} を詳細分析中..."):
            try:
                # 個別も頑丈な方法に変更
                stock = yf.Ticker(ticker)
                df = stock.history(period=f"{days}d")
                
                if df.empty:
                    st.error("データが見つかりません。コードを確認してください。")
                else:
                    # テクニカル計算
                    df['SMA20'] = df['Close'].rolling(20).mean()
                    df['SMA50'] = df['Close'].rolling(50).mean()
                    
                    delta = df['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rs = gain / loss
                    df['RSI'] = 100 - (100 / (1 + rs))

                    # 1. 大きなチャート (Pro仕様)
                    fig = go.Figure()
                    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='ローソク'))
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], line=dict(color='orange'), name='SMA20'))
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], line=dict(color='blue'), name='SMA50'))
                    fig.update_layout(title=f"{ticker} 詳細チャート", height=600)
                    st.plotly_chart(fig, use_container_width=True)

                    # 2. 詳細レポート
                    st.subheader("🤖 Gemini先生の分析レポート")
                    last = df.iloc[-1]
                    prompt = f"""
                    あなたはプロの株式アナリストです。
                    銘柄: {ticker}
                    現在値: {last['Close']:.2f}
                    RSI(14): {last['RSI']:.2f}
                    
                    1. トレンド分析
                    2. 売買シグナル (今買うべきか？)
                    3. 戦略 (エントリー・損切り)
                    を日本語で簡潔に。
                    """
                    res = model.generate_content(prompt)
                    st.markdown(res.text)
            except Exception as e:
                st.error(f"エラー: {e}")
    
    # 何も押してない時
    else:
        st.info("👈 左のメニューから「チャート分析」か「スクリーニング」を選んでください。")

else:
    st.warning("👈 左上の欄にAPIキーを入れてください")