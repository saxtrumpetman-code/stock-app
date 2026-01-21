import streamlit as st
import google.generativeai as genai
import plotly.graph_objects as go
import yfinance as yf

# --- 設定 ---
MODEL_NAME = "gemini-flash-latest"

st.set_page_config(page_title="かんたん株AI", layout="wide")
st.title("📈 かんたん株AI")

# --- 左側のメニュー（ここだけ触ればOK） ---
with st.sidebar:
    st.header("1. 鍵を入れる")
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except:
        api_key = st.text_input("Gemini APIキー", type="password")

    st.divider()

    st.header("2. 何を見る？")
    
    # ★ ここにご希望のボタンを置きました！ ★
    mode = "manual"
    target_list = []

    if st.button("💰 お宝！低位株 (安い株)", type="primary"):
        mode = "scan"
        # 楽天、ENEOS、日産、ZHD、セブン銀行
        target_list = ["4755.T", "5020.T", "7201.T", "4689.T", "8410.T"]
        st.success("安い株を探しています！")

    if st.button("🏆 王道！大型株 (有名)", type="primary"):
        mode = "scan"
        # トヨタ、三菱UFJ、ソニー、任天堂
        target_list = ["7203.T", "8306.T", "6758.T", "7974.T"]
        st.success("有名な株を見ています！")

    st.write("--- または ---")

    # 自分で入れる場所
    manual_code = st.text_input("コードを入れる (例: 7203.T)", value="7203.T")
    st.caption("※日本株は数字のあとに .T をつけてね")
    
    if st.button("この株を調べる"):
        mode = "manual"

# --- メイン画面 ---
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)

    # 調べるリストを決める
    if mode == "scan":
        tickers = target_list
    else:
        tickers = [manual_code]

    # --- 順番に調べる ---
    for ticker in tickers:
        try:
            # データを取る
            df = yf.download(ticker, period="180d", interval="1d", progress=False)
            
            if df.empty:
                st.error(f"「{ticker}」が見つからないよ。コード合ってる？")
            else:
                # RSI（買われすぎ・売られすぎ）だけ計算
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                last_rsi = rsi.iloc[-1]
                last_price = df['Close'].iloc[-1]

                # 枠線をつけて見やすく表示
                with st.container(border=True):
                    col_img, col_text = st.columns([2, 1])

                    with col_img:
                        st.subheader(f"{ticker} のチャート")
                        # チャートを描く
                        fig = go.Figure()
                        fig.add_trace