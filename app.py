import streamlit as st
import yfinance as yf
import google.generativeai as genai
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import concurrent.futures

# ==========================================
# 🔑 設定
# ==========================================
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("鍵（Secrets）が設定されていません。")
    st.stop()

MODEL_NAME = "gemini-2.5-flash"

st.set_page_config(page_title="トレーダーズ・ステーション Pro", layout="wide")

# ==========================================
# 🧠 計算関数群
# ==========================================
def calculate_lines(df, window=20):
    df['Resistance'] = df['High'].rolling(window=window).max()
    df['Support'] = df['Low'].rolling(window=window).min()
    x = np.arange(len(df))
    y = (df['High'].values + df['Low'].values) / 2
    slope, intercept = np.polyfit(x, y, 1)
    df['Trend_Slope'] = slope
    df['Trend_Center'] = slope * x + intercept
    std_dev = np.std(y - df['Trend_Center'])
    df['Trend_Upper'] = df['Trend_Center'] + (2 * std_dev)
    df['Trend_Lower'] = df['Trend_Center'] - (2 * std_dev)
    return df

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# 🚀 データ取得関数 (コードも返すように修正)
def fetch_and_analyze(item):
    name, code = item
    if code == "": return None
    try:
        stock_data = yf.Ticker(code).history(period="3mo")
        if stock_data.empty: return None
        
        current_price = stock_data['Close'].iloc[-1]
        rsi_series = calculate_rsi(stock_data['Close'])
        current_rsi = rsi_series.iloc[-1]
        
        x = np.arange(len(stock_data))
        slope, _ = np.polyfit(x, stock_data['Close'], 1)
        
        return {
            "code": code, # 👈 ここ重要！コードを持ち帰る
            "name": name,
            "price": current_price,
            "rsi": current_rsi,
            "slope": slope
        }
    except:
        return None

# ==========================================
# 📱 画面表示
# ==========================================
st.subheader("📊 トレーダーズ・ステーション Pro (Turbo)")

with st.sidebar:
    st.header("🔍 爆速スキャナー")
    use_rsi = st.checkbox("RSIで絞り込む", value=True)
    rsi_threshold = st.slider("RSIがこれ以下 (売られすぎ)", 10, 50, 30)
    use_trend = st.checkbox("上昇トレンドのみ", value=False)
    run_screen = st.button("スキャン開始 🚀", type="primary")

area = st.radio("エリア選択", ["🇯🇵 日本", "🇺🇸 米国", "🌏 世界・資源・仮想通貨", "💱 FX (為替)"], horizontal=True)

meigara_list = {}
if area == "🇯🇵 日本":
    category = st.radio("カテゴリー", ["📋 主要・登録", "💰 値がさ", "👛 手頃", "📉 低位・ボロ株", "💎 掘出し物"], horizontal=True)
    if category == "📋 主要・登録": meigara_list = {"🔍 自分で入力": "", "🇯🇵 日経平均": "^N225", "🇯🇵 トヨタ": "7203.T", "🇯🇵 UFJ銀行": "8306.T", "🇯🇵 ソニーG": "6758.T", "🇯🇵 ソフトバンクG": "9984.T"}
    elif category == "💰 値がさ": meigara_list = {"🔍 自分で入力": "", "🇯🇵 ファストリ": "9983.T", "🇯🇵 東エレク": "8035.T", "🇯🇵 キーエンス": "6861.T", "🇯🇵 任天堂": "7974.T"}
    elif category == "👛 手頃": meigara_list = {"🔍 自分で入力": "", "🇯🇵 ENEOS": "5020.T", "🇯🇵 楽天G": "4755.T", "🇯🇵 イオン": "8267.T", "🇯🇵 ホンダ": "7267.T"}
    elif category == "📉 低位・ボロ株": meigara_list = {"🔍 自分で入力": "", "🇯🇵 日産自動車": "7201.T", "🇯🇵 セブン銀行": "8410.T", "🇯🇵 LINEヤフー": "4689.T", "🇯🇵 マツダ": "7261.T", "🇯🇵 NTN": "6472.T"}
    else: meigara_list = {"🔍 自分で入力": "", "🇯🇵 レーザーテック": "6920.T", "🇯🇵 メルカリ": "4385.T", "🇯🇵 カバー": "5253.T", "🇯🇵 QPS研究所": "5595.T", "🇯🇵 さくらネット": "3778.T"}
elif area == "🇺🇸 米国":
    category = st.radio("カテゴリー", ["📋 主要指数", "🚀 M7 (巨大テック)", "🛡️ 高配当・安定", "💎 掘出し・成長株"], horizontal=True)
    if category == "📋 主要指数": meigara_list = {"🔍 自分で入力": "", "🇺🇸 S&P 500": "SPY", "🇺🇸 ナスダック100": "QQQ", "🇺🇸 ダウ平均": "DIA"}
    elif category == "🚀 M7 (巨大テック)": meigara_list = {"🔍 自分で入力": "", "🇺🇸 NVIDIA": "NVDA", "🇺🇸 Apple": "AAPL", "🇺🇸 Microsoft": "MSFT", "🇺🇸 Amazon": "AMZN", "🇺🇸 Tesla": "TSLA"}
    elif category == "🛡️ 高配当・安定": meigara_list = {"🔍 自分で入力": "", "🇺🇸 コカ・コーラ": "KO", "🇺🇸 P&G": "PG", "🇺🇸 ジョンソン&ジョンソン": "JNJ", "🇺🇸 マクドナルド": "MCD"}
    else: meigara_list = {"🔍 自分で入力": "", "🇺🇸 Palantir": "PLTR", "🇺🇸 Coinbase": "COIN", "🇺🇸 ARM": "ARM", "🇺🇸 Uber": "UBER"}
elif area == "🌏 世界・資源・仮想通貨":
    meigara_list = {"🔍 自分で入力": "", "🥇 金 (Gold)": "GLD", "🛢 原油 (WTI)": "CL=F", "🪙 ビットコイン": "BTC-USD", "🇮🇳 インドSENSEX": "^BSESN", "🇨🇳 香港ハンセン": "^HSI"}
else: # FX
    category = st.radio("カテゴリー", ["🇯🇵 クロス円", "🌎 ドルストレート", "🌶️ 新興国"], horizontal=True)
    if category == "🇯🇵 クロス円": meigara_list = {"🔍 自分で入力": "", "🇺🇸/🇯🇵 ドル円": "USDJPY=X", "🇪🇺/🇯🇵 ユーロ円": "EURJPY=X", "🇬🇧/🇯🇵 ポンド円": "GBPJPY=X", "🇦🇺/🇯🇵 豪ドル円": "AUDJPY=X"}
    elif category == "🌎 ドルストレート": meigara_list = {"🔍 自分で入力": "", "🇪🇺/🇺🇸 ユーロドル": "EURUSD=X", "🇬🇧/🇺🇸 ポンドドル": "GBPUSD=X", "🇦🇺/🇺🇸 豪ドル米ドル": "AUDUSD=X"}
    else: meigara_list = {"🔍 自分で入力": "", "🇲🇽/🇯🇵 メキシコペソ円": "MXNJPY=X", "🇿🇦/🇯🇵 南アランド円": "ZARJPY=X"}

# ------------------------------------
# 🚀 爆速スクリーニング処理
# ------------------------------------
if run_screen:
    target_items = list(meigara_list.items())
    hit_list = []
    
    with st.spinner(f"🚀 全力でスキャン中... ({len(target_items)-1}件)"):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            results = list(executor.map(fetch_and_analyze, target_items))
        
        for res in results:
            if res is None: continue
            is_hit = True
            reason = []
            
            if use_rsi:
                if res['rsi'] <= rsi_threshold:
                    reason.append(f"RSI安すぎ ({res['rsi']:.1f})")
                else:
                    is_hit = False
            
            if use_trend and is_hit:
                if res['slope'] > 0:
                    reason.append("上昇トレンド")
                else:
                    is_hit = False
            
            if is_hit:
                # ここでリストの順番を決める
                hit_list.append({
                    "コード": res['code'], # 👈 ちゃんとしたコードを表示
                    "銘柄名": res['name'],
                    "現在値": f"{res['price']:,.2f}",
                    "RSI": f"{res['rsi']:.1f}",
                    "判定コメント": ", ".join(reason)
                })

    if hit_list:
        st.success(f"💎 {len(hit_list)}件のお宝候補を発見！")
        # hide_index=True で左端の「0」を消す！
        st.dataframe(pd.DataFrame(hit_list), hide_index=True, use_container_width=True)
    else:
        st.warning("条件に合う銘柄はありませんでした。")

# ------------------------------------
# 個別分析エリア
# ------------------------------------
st.markdown("---")
col1, col2 = st.columns([2, 1])
with col1:
    selected_option = st.selectbox(f"銘柄を選んで詳細分析", list(meigara_list.keys()))
    if selected_option == "🔍 自分で入力":
        ticker = st.text_input("コード入力")
    else:
        ticker = meigara_list.get(selected_option, "")

with col2:
    period = st.selectbox("期間", ["1mo", "3mo", "6mo", "1y", "5y"], index=2)

tech_options = st.multiselect("チャート表示", ["📈 トレンドライン", "🧱 サポート・レジスタンス"], default=["📈 トレンドライン", "🧱 サポート・レジスタンス"])

if st.button("AI詳細分析開始 🚀", use_container_width=True):
    if not ticker:
        st.warning("銘柄を選択してください。")
        st.stop()
    with st.spinner(f"{ticker} を分析中..."):
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period)
            if df.empty:
                st.error("データなし")
            else:
                df = calculate_lines(df)
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='価格'))
                if "🧱 サポート・レジスタンス" in tech_options:
                    fig.add_trace(go.Scatter(x=df.index, y=df['Resistance'], mode='lines', line=dict(color='rgba(255, 165, 0, 0.6)', dash='dot'), name='上値抵抗'))
                    fig.add_trace(go.Scatter(x=df.index, y=df['Support'], mode='lines', line=dict(color='rgba(50, 205, 50, 0.6)', dash='dot'), name='下値支持'))
                if "📈 トレンドライン" in tech_options:
                    slope = df['Trend_Slope'].iloc[-1]
                    color = 'rgba(255, 80, 80, 0.9)' if slope > 0 else 'rgba(80, 80, 255, 0.9)'
                    fig.add_trace(go.Scatter(x=df.index, y=df['Trend_Upper'], mode='lines', line=dict(color=color), name='上限'))
                    fig.add_trace(go.Scatter(x=df.index, y=df['Trend_Center'], mode='lines', line=dict(color=color, dash='dash'), name='中心'))
                    fig.add_trace(go.Scatter(x=df.index, y=df['Trend_Lower'], mode='lines', line=dict(color=color), showlegend=False))
                fig.update_layout(title=f"{ticker} 解析チャート", height=500, xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
                
                current_price = df['Close'].iloc[-1]
                change = ((current_price - df['Close'].iloc[0]) / df['Close'].iloc[0]) * 100
                rsi_val = calculate_rsi(df['Close']).iloc[-1]
                prompt = f"""
                プロ投資家として{ticker}を分析。
                価格: {current_price:.2f}, 変動: {change:.2f}%, RSI: {rsi_val:.2f}, トレンド: {'上昇' if slope > 0 else '下降'}
                【レポート】
                1. 📈 トレンド診断
                2. ⚖️ 需給と節目
                3. 🔮 売買戦略
                """
                genai.configure(api_key=API_KEY)
                model = genai.GenerativeModel(MODEL_NAME)
                response = model.generate_content(prompt)
                st.info("📊 分析レポート")
                st.markdown(response.text)
        except Exception as e:
            st.error(f"エラー: {e}")