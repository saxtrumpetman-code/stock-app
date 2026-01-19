import streamlit as st
import yfinance as yf
import google.generativeai as genai
import plotly.graph_objects as go
import numpy as np # 🧮 数学計算用

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
# 🧠 テクニカル計算関数
# ==========================================
def calculate_lines(df, window=20):
    """
    1. 水平の需給ライン
    2. 斜めのトレンドライン（色判定用の傾きも計算）
    """
    # --- A. 水平ライン (需給の壁) ---
    df['Resistance'] = df['High'].rolling(window=window).max()
    df['Support'] = df['Low'].rolling(window=window).min()
    
    # --- B. トレンドライン (線形回帰) ---
    x = np.arange(len(df))
    y = (df['High'].values + df['Low'].values) / 2
    
    # 1次関数 (y = ax + b) で近似
    slope, intercept = np.polyfit(x, y, 1)
    
    # 傾きをデータフレームに保存（色分け判定用）
    df['Trend_Slope'] = slope
    
    # 中心線とバンド計算
    df['Trend_Center'] = slope * x + intercept
    std_dev = np.std(y - df['Trend_Center'])
    df['Trend_Upper'] = df['Trend_Center'] + (2 * std_dev)
    df['Trend_Lower'] = df['Trend_Center'] - (2 * std_dev)

    return df

# ==========================================
# 📱 画面表示
# ==========================================
st.subheader("📊 トレーダーズ・ステーション Pro")

# 🔘 エリア選択
area = st.radio(
    "エリアを選択してください",
    ["🇯🇵 日本", "🇺🇸 米国", "🌏 世界・資源・仮想通貨", "💱 FX (為替)"],
    horizontal=True,
    index=3
)

meigara_list = {}

# ------------------------------------
# 銘柄リスト定義
# ------------------------------------
if area == "🇯🇵 日本":
    category = st.radio("カテゴリー", ["📋 主要・登録", "💰 値がさ", "👛 手頃", "📉 低位・ボロ株", "💎 掘出し物"], horizontal=True)
    if category == "📋 主要・登録": meigara_list = {"🔍 自分で入力": "", "🇯🇵 日経平均": "^N225", "🇯🇵 トヨタ": "7203.T", "🇯🇵 UFJ銀行": "8306.T", "🇯🇵 ソニーG": "6758.T", "🇯🇵 ソフトバンクG": "9984.T"}
    elif category == "💰 値がさ": meigara_list = {"🔍 自分で入力": "", "🇯🇵 ファストリ": "9983.T", "🇯🇵 東エレク": "8035.T", "🇯🇵 キーエンス": "6861.T", "🇯🇵 任天堂": "7974.T"}
    elif category == "👛 手頃": meigara_list = {"🔍 自分で入力": "", "🇯🇵 ENEOS": "5020.T", "🇯🇵 楽天G": "4755.T", "🇯🇵 イオン": "8267.T", "🇯🇵 ホンダ": "7267.T"}
    elif category == "📉 低位・ボロ株": meigara_list = {"🔍 自分で入力": "", "🇯🇵 日産自動車": "7201.T", "🇯🇵 セブン銀行": "8410.T", "🇯🇵 LINEヤフー": "4689.T"}
    else: meigara_list = {"🔍 自分で入力": "", "🇯🇵 レーザーテック": "6920.T", "🇯🇵 メルカリ": "4385.T", "🇯🇵 カバー": "5253.T", "🇯🇵 QPS研究所": "5595.T"}

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
# 選択と分析実行
# ------------------------------------
col1, col2 = st.columns([2, 1])
with col1:
    selected_option = st.selectbox(f"銘柄リスト", list(meigara_list.keys()))
    if selected_option == "🔍 自分で入力":
        ticker = st.text_input("コード入力 (例: 7203.T, USDJPY=X)")
    else:
        ticker = meigara_list.get(selected_option, "")
        st.code(f"選択中: {ticker}")

with col2:
    period = st.selectbox("期間", ["1mo", "3mo", "6mo", "1y", "5y"], index=2)

tech_options = st.multiselect(
    "表示するラインを選択",
    ["📈 トレンドライン (自動色分け)", "🧱 サポート・レジスタンス (水平)"],
    default=["📈 トレンドライン (自動色分け)", "🧱 サポート・レジスタンス (水平)"]
)

if st.button("AI分析開始 🚀", use_container_width=True):
    if not ticker:
        st.warning("銘柄を選択してください。")
        st.stop()

    with st.spinner(f"{ticker} を徹底分析中..."):
        try:
            # 1. データ取得
            stock = yf.Ticker(ticker)
            df = stock.history(period=period)
            
            if df.empty:
                st.error("データが見つかりません。")
            else:
                # 2. テクニカル計算
                df = calculate_lines(df)
                
                # 3. 高機能チャート描画
                fig = go.Figure()

                # ローソク足
                fig.add_trace(go.Candlestick(
                    x=df.index,
                    open=df['Open'], high=df['High'],
                    low=df['Low'], close=df['Close'],
                    name='ローソク足'
                ))

                # A. 水平ライン
                if "🧱 サポート・レジスタンス (水平)" in tech_options:
                    fig.add_trace(go.Scatter(
                        x=df.index, y=df['Resistance'], mode='lines', name='上値抵抗 (水平)',
                        line=dict(color='rgba(255, 165, 0, 0.6)', width=1, dash='dot') # オレンジ
                    ))
                    fig.add_trace(go.Scatter(
                        x=df.index, y=df['Support'], mode='lines', name='下値支持 (水平)',
                        line=dict(color='rgba(50, 205, 50, 0.6)', width=1, dash='dot') # ライムグリーン
                    ))

                # B. トレンドライン (自動色分け判定)
                if "📈 トレンドライン (自動色分け)" in tech_options:
                    # 傾きを取得
                    slope = df['Trend_Slope'].iloc[-1]
                    
                    if slope > 0:
                        # 上昇トレンド (赤) 🟥
                        trend_color = 'rgba(255, 80, 80, 0.9)'
                        trend_name = "上昇トレンド (強)"
                    else:
                        # 下降トレンド (青) 🟦
                        trend_color = 'rgba(80, 80, 255, 0.9)'
                        trend_name = "下降トレンド (弱)"

                    # 上限ライン (+2σ)
                    fig.add_trace(go.Scatter(
                        x=df.index, y=df['Trend_Upper'], mode='lines', name=trend_name,
                        line=dict(color=trend_color, width=1.5)
                    ))
                    # 中心ライン
                    fig.add_trace(go.Scatter(
                        x=df.index, y=df['Trend_Center'], mode='lines', name='中心線',
                        line=dict(color=trend_color, width=1, dash='dash')
                    ))
                    # 下限ライン (-2σ)
                    fig.add_trace(go.Scatter(
                        x=df.index, y=df['Trend_Lower'], mode='lines', showlegend=False,
                        line=dict(color=trend_color, width=1.5)
                    ))

                fig.update_layout(
                    title=f"{ticker} 需給・トレンド解析チャート",
                    yaxis_title="価格",
                    xaxis_rangeslider_visible=False,
                    height=600,
                    margin=dict(l=20, r=20, t=50, b=20)
                )
                
                st.plotly_chart(fig, use_container_width=True)

                # 4. AI分析
                current_price = df['Close'].iloc[-1]
                start_price = df['Close'].iloc[0]
                change = ((current_price - start_price) / start_price) * 100
                
                unit_hint = "円" if ".T" in ticker or "JPY=X" in ticker else "ドル/現地通貨"
                
                role_text = "あなたは需給とトレンドを読むプロのストラテジストです。"
                if area == "💱 FX (為替)":
                    role_text = "あなたは熟練の為替ディーラーです。トレンドラインや金利差を重視します。"

                prompt = f"""
                {role_text}
                以下の市場データ（{ticker}）を分析してください。
                現在値: {current_price:.2f} ({unit_hint})
                期間内変動: {change:.2f}%
                トレンドの傾き: {'上昇' if df['Trend_Slope'].iloc[-1] > 0 else '下降'}
                
                【レポート構成】
                1. 📈 **トレンド分析 (重要)**
                   - トレンドラインは赤（上昇）か青（下降）か？
                   - 現在位置はバンドの上限・下限に近いか？
                2. ⚖️ **需給バランス**
                   - 売りと買いの強さ。
                3. 📰 **ファンダメンタルズ**
                   - 背景にあるニュースや経済指標。
                4. 🔮 **売買シナリオ**
                   - 短期のターゲット価格と損切りポイントの目安。
                """

                genai.configure(api_key=API_KEY)
                model = genai.GenerativeModel(MODEL_NAME)
                response = model.generate_content(prompt)

                st.info(f"📊 {ticker} 詳細分析レポート")
                st.markdown(response.text)

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")