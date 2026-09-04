import streamlit as st
import google.generativeai as genai
import plotly.graph_objects as go
import yfinance as yf
import time

# --- 設定: エラーが出たこの名前が、実は正解でした ---
MODEL_NAME = "gemini-flash-latest"

st.set_page_config(page_title="トレードAI分析 Pro", layout="wide")
st.title("📈 トレードAI分析 Pro (不屈の再試行版)")

# --- サイドバー ---
with st.sidebar:
    st.header("1. 設定")
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except:
        api_key = st.text_input("Gemini APIキー", type="password")

    st.divider()

    st.header("2. 個別分析")
    ticker = st.text_input("銘柄コード (例: USDJPY=X, 7203.T)", value="USDJPY=X")
    days = st.slider("期間 (日)", 30, 365, 180)
    btn_single = st.button("🚀 チャート分析を実行", type="primary")

    st.divider()

    st.header("3. 自動スクリーニング")
    st.caption("※制限がかかっても自動で待機して再開します")
    
    btn_low = st.button("💰 日本株：定位株 (低位)")
    btn_large = st.button("🏢 日本株：主力株 (大型)")
    btn_us = st.button("🇺🇸 米国株：人気銘柄")

# --- 関数: 諦めないAI呼び出し ---
def ask_gemini_with_retry(model, prompt):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return model.generate_content(prompt)
        except Exception as e:
            # 429エラー (使いすぎ) なら待つ
            if "429" in str(e) or "Quota" in str(e):
                wait_time = 20 + (attempt * 10) # 20秒, 30秒, 40秒と伸ばす
                st.warning(f"⚠️ 通信制限中... {wait_time}秒待機して再試行します ({attempt+1}/{max_retries})")
                time.sleep(wait_time)
            else:
                # それ以外のエラーは報告して終了
                st.error(f"AIエラー: {e}")
                return None
    st.error("❌ 混雑が激しいため中断しました。時間を空けて試してください。")
    return None

# --- 裁量パネル: AIのトレード判断を統一フォーマットで表示 ---
JUDGMENT_STYLES = {
    "買い": {"color": "#0f9d58", "bg": "#e6f4ea", "icon": "📈"},
    "売り": {"color": "#d93025", "bg": "#fce8e6", "icon": "📉"},
    "様子見": {"color": "#5f6368", "bg": "#f1f3f4", "icon": "⏸️"},
}

def build_judgment_prompt(ticker, price, rsi, currency, detail=True):
    prompt = f"""
銘柄: {ticker} (価格: {price:.2f}{currency}, RSI: {rsi:.1f})
あなたはプロのトレーダーです。以下の【出力フォーマット】に厳密に従い、日本語で回答してください。
項目名と内容は「項目名: 内容」の形式で1行ずつ、改行して出力してください。

【出力フォーマット】
判定: (買い/売り/様子見のいずれか一言)
トレンド: (上昇/下降/レンジのいずれか)
理由: (1〜2文で簡潔に)
"""
    if detail:
        prompt += """エントリー: (目安の価格帯)
損切り: (目安の価格)
利確: (目安の価格)
"""
    return prompt

def parse_judgment_fields(text):
    fields = {}
    for line in text.splitlines():
        sep = ":" if ":" in line else ("：" if "：" in line else None)
        if not sep:
            continue
        key, _, value = line.partition(sep)
        key = key.strip().lstrip("#*- ").strip()
        value = value.strip()
        if key and value:
            fields[key] = value
    return fields

def render_judgment_panel(text, compact=False):
    fields = parse_judgment_fields(text)
    judgment = fields.get("判定", "").strip()
    style = JUDGMENT_STYLES.get(judgment, JUDGMENT_STYLES["様子見"])

    st.markdown(
        f"""<div style="border-left:6px solid {style['color']}; background:{style['bg']};
        padding:10px 14px; border-radius:6px; margin-bottom:8px;">
        <span style="font-size:1.1em; font-weight:700; color:{style['color']};">
        {style['icon']} 判定: {judgment or '不明'}</span></div>""",
        unsafe_allow_html=True,
    )

    if not fields:
        st.markdown(text)
        return

    if fields.get("トレンド"):
        st.markdown(f"**トレンド**: {fields['トレンド']}")
    if fields.get("理由"):
        st.markdown(f"**理由**: {fields['理由']}")

    if not compact:
        for label in ["エントリー", "損切り", "利確"]:
            if fields.get(label):
                st.markdown(f"**{label}**: {fields[label]}")

# --- メイン処理 ---
if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)

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
                col_chart, col_ai = st.columns([2, 1])
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

                        with col_ai:
                            st.metric("株価", f"{last_price:.2f} {currency}", f"RSI: {rsi:.1f}")

                            prompt = build_judgment_prompt(t, last_price, rsi, currency, detail=False)

                            # ★ここが変わりました：粘り強い呼び出し★
                            res = ask_gemini_with_retry(model, prompt)
                            if res:
                                render_judgment_panel(res.text, compact=True)

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

                    # レポート
                    st.divider()
                    st.subheader("🤖 Gemini先生の投資判断")
                    last = df.iloc[-1]
                    currency = "$" if "T" not in ticker and "=X" not in ticker else "円"

                    prompt = build_judgment_prompt(ticker, last['Close'], last['RSI'], currency, detail=True)

                    # ★粘り強い呼び出し★
                    res = ask_gemini_with_retry(model, prompt)
                    if res:
                        render_judgment_panel(res.text, compact=False)

            except Exception as e:
                st.error(f"システムエラー: {e}")

    else:
        st.info("👈 左側のメニューから分析モードを選んでください。")
else:
    st.warning("👈 左上にAPIキーを入れてください")