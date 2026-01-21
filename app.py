import streamlit as st
import google.generativeai as genai
import plotly.graph_objects as go
import yfinance as yf
import time  # エラー回避のための休憩用

# --- 設定 ---
MODEL_NAME = "gemini-flash-latest"

st.set_page_config(page_title="トレードAI実況", layout="wide")
st.title("🎙️ トレードAI実況解説 (スクリーニング付)")

# --- サイドバー (機能の司令塔) ---
with st.sidebar:
    st.header("1. 設定")
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except:
        api_key = st.text_input("Gemini APIキー", type="password")

    st.divider()

    # --- ① 個別銘柄の分析 ---
    st.header("2. 個別銘柄の実況")
    ticker = st.text_input("コード入力 (例: 7203.T, NVDA)", value="7203.T")
    days = st.slider("期間 (日)", 30, 365, 180)
    
    # 個別分析ボタン
    btn_single = st.button("🚀 チャート実況スタート", type="primary")

    st.divider()

    # --- ② 自動スクリーニング (お宝探し) ---
    st.header("3. 自動スクリーニング")
    st.caption("ボタンを押すと、AIが順番に実況します")
    
    btn_low = st.button("💰 日本株：定位株 (低位)")
    btn_large = st.button("🏢 日本株：主力株 (大型)")
    btn_us = st.button("🇺🇸 米国株：人気銘柄")

# --- メイン処理 ---
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)

    # ========================================================
    # パターンA：スクリーニング実況 (リストを連続分析)
    # ========================================================
    if btn_low or btn_large or btn_us:
        # リストの準備
        if btn_low:
            target_list = ["4755.T", "5020.T", "7201.T", "4689.T", "8410.T"]
            st.subheader("💰 定位株（低位株）の連続実況")
        elif btn_large:
            target_list = ["7203.T", "8306.T", "9984.T", "6758.T", "8035.T"]
            st.subheader("🏢 主力株（大型株）の連続実況")
        else:
            target_list = ["NVDA", "TSLA", "AAPL", "MSFT", "AMZN"]
            st.subheader("🇺🇸 米国人気株の連続実況")

        # 進行バー
        bar = st.progress(0)
        status = st.empty()

        # ループ処理
        for i, t in enumerate(target_list):
            status.text(f"🎙️ {t} を解説中... ({i+1}/{len(target_list)})")
            
            with st.container(border=True):
                col_chart, col_ai = st.columns([2, 1])
                
                try:
                    # データ取得
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

                        # 右：AI判定（読み上げ式）
                        with col_ai:
                            st.metric("現在値", f"{last_price:.2f} {currency}", f"RSI: {rsi:.1f}")
                            
                            # ★ここが変更点：読み上げ用のプロンプト★
                            prompt = f"""
                            あなたは経済ニュースのキャスターです。
                            銘柄: {t} (価格:{last_price:.2f}, RSI:{rsi:.1f})
                            
                            この株の今の状況を、視聴者に語りかけるような「読み上げ口調（話し言葉）」で短く解説してください。
                            「〜です。〜ます。」調を使い、結論（買いか売りか）を明確に伝えてください。
                            """
                            
                            try:
                                res = model.generate_content(prompt)
                                st.info(res.text) # AIの実況コメント
                            except Exception as e:
                                if "429" in str(e):
                                    st.warning("⚠️ 少し休憩中...")
                                else:
                                    st.error("AIエラー")
                
                except Exception as e:
                    st.error(f"エラー: {e}")
            
            # プログレスバー更新
            bar.progress((i + 1) / len(target_list))
            time.sleep(3) # エラー防止の休憩
            
        status.success("✅ 全銘柄の実況が終了しました！")

    # ========================================================
    # パターンB：個別詳細実況 (Pro画面)
    # ========================================================
    elif btn_single:
        with st.spinner(f"🎙️ {ticker} の詳細データを解析中..."):
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

                    # 2. 実況レポート（読み上げ式）
                    st.divider()
                    st.subheader("🎙️ Geminiキャスターの相場解説")
                    last = df.iloc[-1]
                    
                    # ★ここが変更点：長文の読み上げ用プロンプト★
                    prompt = f"""
                    あなたはベテランの相場解説者です。
                    銘柄: {ticker}
                    現在値: {last['Close']:.2f}
                    RSI(14): {last['RSI']:.2f}
                    
                    この銘柄の現状を、ラジオ番組でリスナーに語りかけるような「丁寧な話し言葉」で解説してください。
                    箇条書きは使わず、自然な文章で構成してください。
                    
                    以下の流れで話してください：
                    1. まず、今のトレンドがどうなっているか（上がっているか下がっているか）。
                    2. 次に、今が「買い時」なのか「売り時」なのか、ズバリ判定。
                    3. 最後に、どこでエントリーしてどこで損切りすべきかのアドバイス。
                    """
                    res = model.generate_content(prompt)
                    
                    # 吹き出しのように表示
                    st.markdown(f"""
                    <div style="background-color:#f0f2f6; padding:20px; border-radius:10px; border-left: 5px solid #ff4b4b;">
                        {res.text}
                    </div>
                    """, unsafe_allow_html=True)

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")

    else:
        st.info("👈 左側のメニューから、実況したい銘柄やリストを選んでください。")

else:
    st.warning("👈 左上の欄にAPIキーを入力してください")