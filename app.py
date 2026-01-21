import streamlit as st
import google.generativeai as genai
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd

# --- 設定 ---
# 動作が最も安定しているモデル
MODEL_NAME = "gemini-flash-latest"

st.set_page_config(page_title="株式トレードAI分析 Pro", layout="wide")
st.title("📈 株式トレードAI分析 Pro")

# --- サイドバー (設定エリア) ---
with st.sidebar:
    st.header("⚙️ 設定メニュー")
    
    # APIキー
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except:
        api_key = st.text_input("🔑 Gemini APIキー", type="password")

    st.divider()

    # 銘柄入力 (デフォルトをトヨタにしました)
    st.subheader("銘柄コード")
    ticker = st.text_input("コードを入力してください", value="7203.T")
    
    st.info("""
    **📝 入力のルール**
    * **日本株**: 数字 + `.T` (例: `7203.T`, `9984.T`)
    * **米国株**: ティッカー (例: `NVDA`, `AAPL`)
    """)
    
    st.divider()
    
    days = st.slider("📅 分析期間 (日)", 30, 365, 180)
    
    st.write("") 
    # 実行ボタン
    run_btn = st.button("🚀 株価を分析する", type="primary", use_container_width=True)

# --- メイン画面 (親切設計) ---

# 1. まだボタンを押していない時（ガイドを表示）
if not run_btn:
    st.info("👈 左側のサイドバーで銘柄を入れて「分析する」を押してください")
    
    st.subheader("🌟 使い方ガイド")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🇯🇵 日本株の場合")
        st.write("証券コードの後に **`.T`** をつけます。")
        st.code("7203.T  (トヨタ自動車)\n8306.T  (三菱UFJ)\n6920.T  (レーザーテック)", language="text")
        
    with col2:
        st.markdown("### 🇺🇸 米国株の場合")
        st.write("アルファベットのシンボルを入力します。")
        st.code("NVDA  (NVIDIA)\nTSLA  (Tesla)\nMSFT  (Microsoft)", language="text")

    st.warning("⚠️ エラーが出る場合は、コードの末尾に `.T` がついているか確認してください。")

# 2. ボタンが押されたら分析開始
else:
    if not api_key:
        st.error("⚠️ サイドバーでAPIキーを設定してください")
    else:
        genai.configure(api_key=api_key)
        
        with st.spinner(f"🔍 {ticker} の株価データを分析中..."):
            try:
                # データ取得
                df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False)
                
                if df.empty:
                    st.error(f"❌ データが見つかりません。「{ticker}」のコードを確認してください。")
                    st.info("ヒント: 日本株なら `7203` ではなく `7203.T` と入力してください。")
                else:
                    # テクニカル指標の計算
                    # 移動平均線
                    df['SMA25'] = df['Close'].rolling(window=25).mean()
                    df['SMA75'] = df['Close'].rolling(window=75).mean()
                    
                    # RSI (相対力指数)
                    delta = df['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    df['RSI'] = 100 - (100 / (1 + rs))

                    # --- ① チャート表示 ---
                    st.subheader(f"📊 {ticker} 株価チャート")
                    
                    fig = go.Figure()
                    # ローソク足
                    fig.add_trace(go.Candlestick(
                        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                        name='ローソク足'
                    ))
                    # 移動平均線 (株によく使われる25日/75日)
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA25'], line=dict(color='orange', width=1), name='25日移動平均'))
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA75'], line=dict(color='blue', width=1), name='75日移動平均'))
                    
                    fig.update_layout(height=500, xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)

                    # --- ② AI分析レポート ---
                    st.divider()
                    st.subheader("🤖 Gemini先生の株式診断")
                    
                    model = genai.GenerativeModel(MODEL_NAME)
                    
                    # AIに渡す最新データ
                    last_price = df['Close'].iloc[-1]
                    last_rsi = df['RSI'].iloc[-1]
                    
                    # 株式専用プロンプト
                    prompt = f"""
                    あなたはプロの株式アナリストです。
                    以下の株価データとテクニカル指標に基づき、投資判断を行ってください。
                    
                    対象銘柄: {ticker}
                    現在値: {last_price:.2f}
                    RSI(14): {last_rsi:.2f}
                    
                    以下の項目を【日本語】で、投資家向けにわかりやすく解説してください：
                    
                    1. **トレンド分析**: 現在は上昇トレンドか、下降トレンドか？
                    2. **売買シグナル**:
                       - 今は「買い時」か？「売り時」か？それとも「様子見」か？
                       - RSIの数値（{last_rsi:.1f}）から見た過熱感は？
                    3. **投資戦略**:
                       - どの価格帯でエントリーすべきか？
                       - 損切りの目安はどこか？
                    
                    ※結論を先にズバリと述べてください。
                    """
                    
                    response = model.generate_content(prompt)
                    st.markdown(response.text)

            except Exception as e:
                st.error(f"エラーが発生しました: {e}")