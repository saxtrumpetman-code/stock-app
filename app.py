import streamlit as st
import plotly.graph_objects as go
import yfinance as yf
import time

st.set_page_config(page_title="トレード分析 Pro", layout="wide")
st.title("📈 トレード分析 Pro")

# --- サイドバー ---
with st.sidebar:
    st.header("1. 個別分析")
    ticker = st.text_input("銘柄コード (例: USDJPY=X, 7203.T)", value="USDJPY=X")
    days = st.slider("期間 (日)", 30, 365, 180)
    btn_single = st.button("🚀 チャート分析を実行", type="primary")

    st.divider()

    st.header("2. 自動スクリーニング")
    btn_low = st.button("💰 日本株：定位株 (低位)")
    btn_large = st.button("🏢 日本株：主力株 (大型)")
    btn_us = st.button("🇺🇸 米国株：人気銘柄")

# --- 関数: RSIによる簡易判定 ---
def rsi_signal(rsi):
    if rsi < 30:
        return "売られすぎ（反発の可能性）"
    if rsi > 70:
        return "買われすぎ（反落の可能性）"
    return "中立"

# --- メイン処理 ---
# ========================================================
# パターンA：スクリーニング (リスト連続分析)
# ========================================================
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
            col_chart, col_info = st.columns([2, 1])
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

                    with col_info:
                        st.metric("株価", f"{last_price:.2f} {currency}", f"RSI: {rsi:.1f}")
                        st.info(rsi_signal(rsi))

            except Exception as e:
                st.error(f"データエラー: {e}")
        
        bar.progress((i + 1) / len(target_list))
        time.sleep(2) # 基本休憩
        
    status.success("✅ スキャン完了")

# ========================================================
# パターンB：個別分析 (FX売り対応)
# ========================================================
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
                delta = df['Close'].diff()
                rs = (delta.where(delta > 0, 0)).rolling(14).mean() / (-delta.where(delta < 0, 0)).rolling(14).mean()
                df['RSI'] = 100 - (100 / (1 + rs))

                # チャート
                st.subheader(f"📊 {ticker} 詳細チャート")
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='ローソク'))
                fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], line=dict(color='orange'), name='SMA20'))
                fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], line=dict(color='blue'), name='SMA50'))
                fig.update_layout(height=600, xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)

                # 指標サマリー
                st.divider()
                st.subheader("📋 テクニカル指標")
                last = df.iloc[-1]
                c1, c2, c3 = st.columns(3)
                c1.metric("現在値", f"{last['Close']:.2f}")
                c2.metric("RSI(14)", f"{last['RSI']:.1f}")
                c3.metric("判定", rsi_signal(last['RSI']))

        except Exception as e:
            st.error(f"システムエラー: {e}")

else:
    st.info("👈 左側のメニューから分析モードを選んでください。")
