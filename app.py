import streamlit as st
import yfinance as yf
import google.generativeai as genai
from gtts import gTTS
import io
import streamlit.components.v1 as components # 自動スクロール用

# ==========================================
# 🔑 設定
# ==========================================
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("鍵（Secrets）が設定されていません。")
    st.stop()

MODEL_NAME = "gemini-2.5-flash"

st.set_page_config(page_title="世界株ステーション", layout="wide")

# ⚓️ ここが「ページの一番上」
st.markdown('<div id="top_anchor"></div>', unsafe_allow_html=True)

# ==========================================
# 📱 画面表示
# ==========================================
st.subheader("🌏 世界の株ステーション")

# 🔥 世界の主要銘柄・指数リスト
meigara_list = {
    "🔍 自分で入力する": "",
    
    # 🇺🇸 米国
    "🇺🇸 S&P 500 (SPY)": "SPY",
    "🇺🇸 NVIDIA (NVDA)": "NVDA",
    "🇺🇸 Apple (AAPL)": "AAPL",
    "🇺🇸 Tesla (TSLA)": "TSLA",

    # 🇯🇵 日本
    "🇯🇵 日経平均株価 (^N225)": "^N225",
    "🇯🇵 トヨタ自動車 (7203)": "7203.T",
    "🇯🇵 三菱UFJ銀行 (8306)": "8306.T",
    "🇯🇵 ソフトバンクG (9984)": "9984.T",

    # 🇮🇳🇨🇳 その他
    "🇮🇳 インドSENSEX (^BSESN)": "^BSESN",
    "🇨🇳 香港ハンセン指数 (^HSI)": "^HSI",
    "🥇 金 (Gold)": "GLD",
    "🪙 ビットコイン (BTC)": "BTC-USD"
}

# 選択ボックス
col1, col2 = st.columns([2, 1])
with col1:
    selected_option = st.selectbox("エリア・銘柄を選択", list(meigara_list.keys()))
    
    if selected_option == "🔍 自分で入力する":
        ticker = st.text_input("コード入力（例: NVDA, 9984.T）", value="NVDA")
    else:
        ticker = meigara_list[selected_option]
        st.code(f"選択中: {ticker}")

with col2:
    period = st.selectbox("期間", ["1mo", "3mo", "6mo", "1y", "5y"], index=2)

if st.button("AI分析開始 🚀", use_container_width=True):
    with st.spinner(f"🌍 {ticker} のデータを分析中..."):
        try:
            # 1. データ取得
            stock = yf.Ticker(ticker)
            df = stock.history(period=period)
            
            if df.empty:
                st.error("データが見つかりません。市場が休場中か、コードが間違っている可能性があります。")
            else:
                # 2. チャート表示
                st.line_chart(df['Close'])

                # 3. テクニカル計算
                current_price = df['Close'].iloc[-1]
                start_price = df['Close'].iloc[0]
                change = ((current_price - start_price) / start_price) * 100
                unit_hint = "円" if ".T" in ticker else "ドル/現地通貨"

                # 4. AIへの命令（シンプルかつ的確に）
                prompt = f"""
                あなたは世界経済に精通したグローバル投資家です。
                以下の市場データ（{ticker}）を分析してください。
                
                現在値: {current_price:.2f} ({unit_hint})
                期間内変動: {change:.2f}%
                
                【リクエスト】
                1. トレンド判定（上昇/下落/レンジ）
                2. 世界的な注目度や背景ニュース
                3. 今後のシナリオとリスク要因
                4. 初心者への一言アドバイス
                
                ※スマホで読むため、箇条書きで短くまとめてください。
                """

                genai.configure(api_key=API_KEY)
                model = genai.GenerativeModel(MODEL_NAME)
                response = model.generate_content(prompt)

                # ⚓️ ここが「解説」の到着地点
                st.markdown('<div id="result_anchor"></div>', unsafe_allow_html=True)

                # 5. 結果表示
                st.info(f"📊 {ticker} 分析レポート")
                st.markdown(response.text)
                
                # 🗣️ 読み上げ機能（標準語モード）
                with st.spinner("音声を生成中...🎙️"):
                    tts = gTTS(text=response.text, lang='ja')
                    audio_bytes = io.BytesIO()
                    tts.write_to_fp(audio_bytes)
                    audio_bytes.seek(0)
                    st.audio(audio_bytes, format='audio/mp3')

                # 🚀 自動スクロール（解説へワープ！）
                js = f"""
                <script>
                    window.location.href = '#result_anchor';
                </script>
                """
                components.html(js, height=0)

                # 🔙 上に戻るボタン
                st.markdown("""
                <a href="#top_anchor" style="
                    display: block; width: 100%; padding: 10px; 
                    background-color: #f0f2f6; text-align: center; 
                    border-radius: 5px; text-decoration: none; color: black; font-weight: bold;
                    border: 1px solid #d6d6d8;
                " target="_self">⬆️ 銘柄選択に戻る</a>
                """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
            