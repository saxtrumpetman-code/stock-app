import streamlit as st
import google.generativeai as genai
import plotly.graph_objects as go
import yfinance as yf
import time  # エラー回避のための休憩用

# --- 設定 ---
MODEL_NAME = "gemini-flash-latest"

st.set_page_config(page_title="トレードAI分析 Pro", layout="wide")
st.title("📈 トレードAI分析 Pro (スクリーニング機能搭載)")

# --- サイドバー (機能の司令塔) ---
with st.sidebar:
    st.header("1. 設定")
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except:
        api_key = st.text_input("Gemini APIキー", type="password")

    st.divider()

    # --- ① 個別銘柄の分析 ---
    st.header("2. 個別銘柄をじっくり")
    ticker = st.text_input("コード入力 (例: 7203.T, NVDA)", value="7203.T")
    days = st.slider("期間 (日)", 30, 365, 180)
    
    # 個別分析ボタン
    btn_single = st.button("🚀 チャート詳細分析", type="primary")

    st.divider()

    # --- ② 自動スクリーニング (お宝探し) ---
    st.header("3. 自動スクリーニング")
    st.caption("ボタンを押すと、AIが順番に診断します")
    
    btn_low = st.button("💰 日本株：定位株 (低位)")
    btn_large = st.button("🏢 日本株：主力株 (大型)")
    btn_us = st.button("🇺🇸 米国株：人気銘柄")

# --- メイン処理 ---
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)

    # ========================================================
    # パターンA：スクリーニング実行 (リストを連続分析)
    # ========================================================
    if btn_low or btn_large or btn_us:
        # リストの準備
        if btn_low:
            target_list = ["4755.T", "5020.T", "7201.T", "4689.T", "8410.T"] # 楽天, ENEOS, 日産...
            st.subheader("💰 定位株（低位株）を一括スキャン")
        elif btn_large:
            target_list = ["7203.T", "8306.T", "9984.T", "6758.T", "8035.T"] # トヨタ, 三菱UFJ...
            st.subheader("🏢 主力株（大型株）を一括スキャン")
        else:
            target_list = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN"] # 米国株
            st.subheader("🇺🇸 米国人気株を一括スキャン")

        # 進行バー
        bar = st.progress(0)
        status = st.empty()

        # ループ処理
        for i, t in enumerate(target_list):
            status.text(f"⏳ 分析中... {t} ({i+1}/{len(target_list)})")
            
            with st.container(border=True):
                col_chart, col_ai = st.columns([2, 1])
                
                try:
                    # データ取得 (最も頑丈な history 方式)
                    stock = yf.Ticker(t)
                    df = stock.history(period="100d")
                    
                    if df.empty:
                        st.error(f"❌ {t}: データなし")
                    else:
                        # 準備
                        last_price = df['Close'].iloc[-1]
                        currency = "$" if "T" not in t else "円"
                        
                        # RSI計算
                        delta = df['Close'].diff()
                        rs = (delta.where(delta > 0, 0)).rolling(14).mean() / (-delta.where(delta < 0, 0)).rolling(14).mean()
                        rsi = 100 - (100 / (1 + rs)).iloc[-1]

                        # 左：ミニチャート
                        with col_chart:
                            st.markdown(f"#### {t}")
                            st.line_chart(df['Close'], height=150)

                        # 右：AI判定
                        with col_ai:
                            st.metric("株価", f"{last_price:.2f} {currency}", f"RSI: {rsi:.1f}")
                            
                            prompt = f"""
                            銘柄: {t} (価格:{last_price:.2f}, RSI:{rsi:.1f})
                            質問: 今は「買い」か「売り」か？
                            回答: ズバリ一言で判定し、理由を1行で述べてください。
                            """
                            
                            # AIエラー回避の再試行ロジック
                            try:
                                res = model.generate_content(prompt)
                                st.info(res.text)
                            except Exception as e:
                                if "429" in str(e):
                                    st.warning("⚠️ 混雑中...スキップします")
                                else:
                                    st.error("AIエラー")
                
                except Exception as e:
                    st.error(f"エラー: {e}")
            
            # プログレスバー更新
            bar.progress((i + 1) / len(target_list))
            
            # ★重要★ 連続アクセスによるエラーを防ぐため3秒待つ
            time.sleep(3)
            
        status.success("✅ スキャン完了しました！")

    # ========================================================
    # パターンB：個別詳細分析 (いつものPro画面)
    # ========================================================
    elif btn_single:
        with st.spinner(f"🔍 {ticker} を詳細分析中..."):
            try:
                stock = yf.Ticker(ticker)
                df = stock.history(period=f"{days}d")
                
                if df.empty:
                    st.error("データが見つかりません。コードを確認してください。")
                else:
                    # テクニカル計算
                    df['SMA20'] = df['Close'].rolling(20).mean()
                    df['SMA50'] = df['Close'].rolling(50).mean()
                    delta = df['Close'].diff()
                    rs = (delta.where(delta > 0, 0)).rolling(14).mean() / (-delta.where(delta < 0, 0)).rolling(14).mean()
                    df['RSI'] = 100 - (100 / (1 + rs))

                    # 1. 本格チャート
                    st.subheader(f"📊 {ticker} 詳細チャート")
                    fig = go.Figure()
                    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='ローソク'))
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], line=dict(color='orange'), name='SMA20'))
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], line=dict(color='blue'), name='SMA50'))
                    fig.update_layout(height=600, xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)

                    # 2. 詳細レポート
                    st.divider()
                    st.subheader("🤖 Gemini先生の投資判断")
                    last = df.iloc[-1]
                    
                    prompt = f"""
                    あなたはプロの投資家です。
                    銘柄: {ticker}
                    現在値: {last['Close']:.2f}
                    RSI(14): {last['RSI']:.2f}
                    
                    以下を日本語で詳しく分析してください:
                    1. トレンド分析 (上昇・下降・レンジ)
                    2. 売買シグナル (買い時・売り時・様子見)
                    3. 具体的な戦略 (エントリー価格、損切りライン)
                    """
                    res = model.generate_content(prompt)
                    st.markdown(res.text)

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")

    # 何もしていない時
    else:
        st.info("👈 左側のメニューから「個別分析」または「スクリーニング」を選んでください。")

else:
    st.warning("👈 左上の欄にAPIキーを入力してください")