import streamlit as st
import google.generativeai as genai
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd

# --- 設定 ---
# 最新の高速モデル（制限がゆるい）
MODEL_NAME = "gemini-flash-latest"

# AIへの命令（FX対応：売りも買いも判定させる）
PROMPT = """
あなたはプロの凄腕トレーダーです。
提供されたチャート（ローソク足、移動平均線、RSI）を分析し、以下のフォーマットで投資判断を行ってください。
FX（為替）や暗号資産も分析対象です。

## 分析結果
1. **トレンド**: [上昇 / 下降 / レンジ] から選択
2. **売買判断**:
   - 【買い (LONG)】: 上昇の押し目、底値反転など
   - 【売り (SHORT)】: 下降の戻り目、天井反転など
   - 【様子見 (WAIT)】: 方向感がない場合
3. **戦略・根拠**:
   - エントリーの根拠（RSIの数値、移動平均線との位置関係など）
   - 損切り(Stop Loss)の目安ライン
   - 利確(Take Profit)の目安

※ 投資助言ではなく、あくまでテクニカル分析の視点として回答してください。
"""

st.set_page_config(page_title="トレードAI分析 Pro", layout="wide")
st.title("📈 トレードAI分析 Pro (FX対応)")

# サイドバー設定
with st.sidebar:
    st.header("設定")
    # APIキー入力
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except:
        api_key = st.text_input("Gemini APIキーを入れてください", type="password")
    
    # 銘柄入力（FXの例を表示）
    ticker = st.text_input("銘柄コード (例: USDJPY=X, 7203.T)", value="USDJPY=X")
    st.caption("※ドル円: USDJPY=X, ユーロドル: EURUSD=X, ビットコイン: BTC-USD")
    
    days = st.slider("期間（日）", 30, 365, 180)
    
    # 分析ボタン
    run_btn = st.button("AI分析を開始", type="primary")

# メイン処理
if run_btn and api_key:
    genai.configure(api_key=api_key)
    
    with st.spinner(f"{ticker} のデータを取得中..."):
        try:
            # データ取得
            df = yf.download(ticker, period=f"{days}d", interval="1d")
            
            if df.empty:
                st.error("データが見つかりませんでした。コードを確認してください。")
            else:
                # テクニカル計算
                # 移動平均線 (SMA)
                df['SMA20'] = df['Close'].rolling(window=20).mean()
                df['SMA50'] = df['Close'].rolling(window=50).mean()
                
                # RSI
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                df['RSI'] = 100 - (100 / (1 + rs))

                # チャート描画
                fig = go.Figure()
                
                # ローソク足
                fig.add_trace(go.Candlestick(
                    x=df.index,
                    open=df['Open'], high=df['High'],
                    low=df['Low'], close=df['Close'],
                    name='ローソク足'
                ))
                
                # SMA
                fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], line=dict(color='orange', width=1), name='SMA20'))
                fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], line=dict(color='blue', width=1), name='SMA50'))
                
                fig.update_layout(title=f"{ticker} チャート", height=600)
                st.plotly_chart(fig, use_container_width=True)

                # AI分析開始
                st.subheader("🤖 Geminiの分析レポート")
                model = genai.GenerativeModel(MODEL_NAME)
                
                # AIに渡すデータを作成（最新の価格データとRSIなどを文字で伝える）
                last_price = df['Close'].iloc[-1]
                last_rsi = df['RSI'].iloc[-1]
                data_summary = f"銘柄: {ticker}, 現在値: {last_price:.2f}, RSI(14): {last_rsi:.2f}"
                
                # チャート画像を送るのは難しいので、テキストデータで補足して質問
                full_prompt = f"{PROMPT}\n\n【最新データ】\n{data_summary}"
                
                with st.chat_message("assistant"):
                    response_placeholder = st.empty()
                    response_placeholder.write("チャートを凝視しています...🧐")
                    
                    try:
                        # グラフの画像化は省略し、テキストデータで判断させる（高速化のため）
                        response = model.generate_content(full_prompt)
                        response_placeholder.markdown(response.text)
                    except Exception as e:
                        st.error(f"AIエラー: {e}")

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")