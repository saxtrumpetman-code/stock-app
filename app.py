import streamlit as st
import google.generativeai as genai
import plotly.graph_objects as go
import yfinance as yf

# --- 設定 ---
MODEL_NAME = "gemini-flash-latest"

st.set_page_config(page_title="かんたん株AI", layout="wide")
st.title("📈 かんたん株AI")

# --- サイドバー ---
with st.sidebar:
    st.header("1. 鍵を入れる")
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except:
        api_key = st.text_input("Gemini APIキー", type="password")

    st.divider()

    st.header("2. 何を見る？")
    
    mode = "manual"
    target_list = []

    # ボタンエリア
    if st.button("💰 お宝！低位株 (安い株)", type="primary"):
        mode = "scan"
        target_list = ["4755.T", "5020.T", "7201.T", "4689.T", "8410.T"]
        st.success("安い株を探しています！")

    if st.button("🏆 王道！大型株 (有名)", type="primary"):
        mode = "scan"
        target_list = ["7203.T", "8306.T", "6758.T", "7974.T"]
        st.success("有名な株を見ています！")

    st.write("--- または ---")

    manual_code = st.text_input("コードを入れる (例: 7203.T)", value="7203.T")
    st.caption("※日本株は .T をつけてね")
    
    if st.button("この株を調べる"):
        mode = "manual"

# --- メイン処理 ---
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)

    # リストの決定
    if mode == "scan":
        tickers = target_list
    else:
        tickers = [manual_code]

    # --- 順番に分析 ---
    for ticker in tickers:
        # データの取得
        df = yf.download(ticker, period="180d", interval="1d", progress=False)
        
        if df.empty:
            st.error(f"❌ 「{ticker}」が見つからないよ。コード合ってる？")
        else:
            # RSI計算
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            last_rsi = rsi.iloc[-1]
            last_price = df['Close'].iloc[-1]

            # 表示エリア
            with st.container(border=True):
                st.subheader(f"{ticker}")
                
                col_chart, col_ai = st.columns([2, 1])

                with col_chart:
                    # チャート作成
                    fig = go.Figure()
                    fig.add_trace(go.Candlestick(
                        x=df.index, 
                        open=df['Open'], 
                        high=df['High'], 
                        low=df['Low'], 
                        close=df['Close']
                    ))
                    fig.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
                    st.plotly_chart(fig, use_container_width=True)

                with col_ai:
                    st.metric("今の値段", f"{last_price:.0f} 円", f"RSI: {last_rsi:.1f}")

                    # AI分析
                    st.write("🤖 **AIの判定**")
                    prompt = f"""
                    あなたは株の先生です。小学生にもわかるように答えてください。
                    銘柄: {ticker} (現在値:{last_price:.0f}円, RSI:{last_rsi:.1f})
                    
                    質問: この株は今、買ったほうがいい？売ったほうがいい？
                    
                    ルール:
                    1. 「買い」「売り」「様子見」のどれかハッキリ言う。
                    2. 理由は1行で簡単・短く言う。
                    """
                    
                    with st.spinner("考え中..."):
                        try:
                            res = model.generate_content(prompt)
                            st.info(res.text)
                        except:
                            st.error("AIが疲れちゃったみたい。もう一回試してね。")

else:
    st.warning("👈 左にAPIキーを入れてね")