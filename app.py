import streamlit as st
import google.generativeai as genai
import plotly.graph_objects as go
import yfinance as yf
import time  # 休憩用

# --- 【修正】元の名前に戻しました（これが正解） ---
MODEL_NAME = "gemini-flash-latest"

st.set_page_config(page_title="トレードAI分析 Pro", layout="wide")
st.title("📈 トレードAI分析 Pro (完全対策版)")

# --- サイドバー ---
with st.sidebar:
    st.header("1. 設定")
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except:
        api_key = st.text_input("Gemini APIキー", type="password")

    st.divider()

    st.header("2. 個別銘柄")
    ticker = st.text_input("銘柄コード (例: 7203.T, NVDA)", value="7203.T")
    days = st.slider("期間 (日)", 30, 365, 180)
    btn_single = st.button("🚀 チャート分析を実行", type="primary")

    st.divider()

    st.header("3. 自動スクリーニング")
    st.caption("※エラー防止のため、ゆっくり分析します")
    btn_low = st.button("💰 日本株：定位株 (低位)")
    btn_large = st.button("🏢 日本株：主力株 (大型)")
    btn_us = st.button("🇺🇸 米国株：人気銘柄")

# --- メイン処理 ---
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)

    # ----------------------------------------
    # パターンA：スクリーニング (連続分析)
    # ----------------------------------------
    if btn_low or btn_large or btn_us:
        if btn_low:
            target_list = ["4755.T", "5020.T", "7201.T", "4689.T", "8410.T"]
            st.subheader("💰 定位株スキャン")
        elif btn_large:
            target_list = ["7203.T", "8306.T", "9984.T", "6758.T", "8035.T"]
            st.subheader("🏢 主力株スキャン")
        else:
            target_list = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN"]
            st.subheader("🇺🇸 米国株スキャン")

        bar = st.progress(0)
        status = st.empty()

        for i, t in enumerate(target_list):
            status.text(f"⏳ 分析中... {t} ({i+1}/{len(target_list)})")
            
            with st.container(border=True):
                col_chart, col_ai = st.columns([2, 1])
                try:
                    # データ取得
                    stock = yf.Ticker(t)
                    df = stock.history(period="100d")
                    
                    if df.empty:
                        st.error(f"❌ {t}: データなし")
                    else:
                        last_price = df['Close'].iloc[-1]
                        currency = "$" if "T" not in t and "=X" not in t else "円"
                        
                        # RSI
                        delta = df['Close'].diff()
                        rs = (delta.where(delta > 0, 0)).rolling(14).mean() / (-delta.where(delta < 0, 0)).rolling(14).mean()
                        rsi = 100 - (100 / (1 + rs)).iloc[-1]

                        with col_chart:
                            st.markdown(f"#### {t}")
                            st.line_chart(df['Close'], height=150)

                        with col_ai:
                            st.metric("株価", f"{last_price:.2f} {currency}", f"RSI: {rsi:.1f}")
                            
                            # プロンプト
                            prompt = f"""
                            銘柄: {t} (価格:{last_price:.2f}, RSI:{rsi:.1f})
                            質問: テクニカル的に「買い」か「売り」か？
                            回答: 結論を一言（買い/売り/様子見）で述べ、理由を1行で。
                            """
                            
                            try:
                                res = model.generate_content(prompt)
                                st.info(res.text)
                            except Exception as e:
                                # 万が一エラーが出ても止まらないようにする
                                if "429" in str(e):
                                    st.warning("⚠️ 混雑中。スキップします。")
                                else:
                                    st.error("AI応答なし")

                except Exception as e:
                    st.error(f"エラー: {e}")
            
            # プログレスバー更新
            bar.progress((i + 1) / len(target_list))
            
            # ★ここが最重要：429エラーを防ぐための休憩時間★
            time.sleep(4) 
            
        status.success("✅ 完了")

    # ----------------------------------------
    # パターンB：個別分析
    # ----------------------------------------
    elif btn_single:
        with st.spinner(f"🔍 {ticker} を分析中..."):
            try:
                stock = yf.Ticker(ticker)
                df = stock.history(period=f"{days}d")
                
                if df.empty:
                    st.error("データが見つかりません。")
                else:
                    df['SMA20'] = df['Close'].rolling(20).mean()
                    df['SMA50'] = df['Close'].rolling(50).mean()
                    
                    # チャート
                    st.subheader(f"📊 {ticker} 詳細チャート")
                    fig = go.Figure()
                    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='ローソク'))
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], line=dict(color='orange'), name='SMA20'))
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], line=dict(color='blue'), name='SMA50'))
                    fig.update_layout(height=600, xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)

                    # レポート
                    st.divider()
                    st.subheader("🤖 Gemini先生の分析")
                    last = df.iloc[-1]
                    prompt = f"""
                    あなたはプロの投資家です。銘柄: {ticker}, 価格: {last['Close']:.2f}
                    1. トレンド分析
                    2. 売買シグナル
                    3. 戦略
                    を日本語で簡潔に分析してください。
                    """
                    try:
                        res = model.generate_content(prompt)
                        st.markdown(res.text)
                    except Exception as e:
                         if "429" in str(e):
                             st.error("⚠️ AIの使いすぎです。数分待ってからやり直してください。")
                         else:
                             st.error(f"AIエラー: {e}")

            except Exception as e:
                st.error(f"システムエラー: {e}")

    else:
        st.info("👈 左側から分析メニューを選んでください")
else:
    st.warning("👈 左上にAPIキーを入れてください")