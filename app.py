import streamlit as st
import yfinance as yf
import google.generativeai as genai

# ==========================================
# 🔑 設定
# ==========================================
# 鍵は自動で読み込まれます
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    # 万が一鍵がない場合のエラー回避
    st.error("鍵（Secrets）が設定されていません。")
    st.stop()

MODEL_NAME = "gemini-2.5-flash"

# スマホで見やすいようにレイアウト設定
st.set_page_config(page_title="株ステーション", layout="wide")

# ==========================================
# 📱 画面の表示（スマホ用にスッキリ化）
# ==========================================
# タイトルを小さくシンプルに
st.subheader("📈 スマホde株分析")

# 入力エリア
col1, col2 = st.columns([2, 1])
with col1:
    ticker = st.text_input("銘柄コード（例: 7203.T, AAPL）", value="7203.T")
with col2:
    period = st.selectbox("期間", ["1mo", "3mo", "6mo", "1y"], index=2)

if st.button("分析する 🚀", use_container_width=True):
    with st.spinner("AIが分析中..."):
        try:
            # 1. 株価データの取得
            stock = yf.Ticker(ticker)
            df = stock.history(period=period)
            
            if df.empty:
                st.error("データが見つかりません。コードを確認してください。")
            else:
                # 2. チャート表示
                st.line_chart(df['Close'])

                # 3. AI分析の準備
                current_price = df['Close'].iloc[-1]
                start_price = df['Close'].iloc[0]
                change = ((current_price - start_price) / start_price) * 100
                
                # AIへの命令
                prompt = f"""
                あなたはプロの投資家です。以下の株価データを分析してください。
                銘柄: {ticker}
                期間: {period}
                現在株価: {current_price:.2f}
                期間内の変動率: {change:.2f}%
                
                以下の点について、スマホで読みやすいように短く箇条書きで教えて：
                1. トレンド（上昇・下落・横ばい）
                2. 注目ポイント
                3. 初心者へのアドバイス（買うべき？待つべき？）
                """

                # AIに聞く
                genai.configure(api_key=API_KEY)
                model = genai.GenerativeModel(MODEL_NAME)
                response = model.generate_content(prompt)

                # 4. 結果表示
                st.info("📊 AIの分析レポート")
                st.markdown(response.text)

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")