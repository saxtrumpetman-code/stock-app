import streamlit as st
import yfinance as yf
import google.generativeai as genai
import plotly.graph_objects as go
import numpy as np
import pandas as pd
import concurrent.futures
from gtts import gTTS
import io
import datetime
import os

# ==========================================
# 🔑 設定
# ==========================================
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("鍵（Secrets）が設定されていません。")
    st.stop()

MODEL_NAME = "gemini-2.5-flash"
HISTORY_FILE = "tracking_history.csv"

st.set_page_config(page_title="トレーダーズ・ステーション Pro", layout="wide")

if "scan_results" not in st.session_state:
    st.session_state.scan_results = None

# ==========================================
# 💾 データ保存・読み込み機能
# ==========================================
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            df = pd.read_csv(HISTORY_FILE)
            df['登録日'] = pd.to_datetime(df['登録日']).dt.date
            return df
        except:
            return pd.DataFrame(columns=['登録日', '銘柄名', 'コード', '登録時株価'])
    return pd.DataFrame(columns=['登録日', '銘柄名', 'コード', '登録時株価'])

def save_history(df):
    df.to_csv(HISTORY_FILE, index=False)

def clean_old_history():
    df = load_history()
    if not df.empty:
        deadline = datetime.date.today() - datetime.timedelta(days=7)
        df = df[df['登録日'] >= deadline]
        save_history(df)

# ==========================================
# 💾 初期リスト設定
# ==========================================
if "my_stock_list" not in st.session_state:
    default_data = {
        "コード": ["^N225", "7203.T", "9984.T"],
        "銘柄名": ["日経平均", "トヨタ", "ソフトバンクG"]
    }
    st.session_state.my_stock_list = pd.DataFrame(default_data)

# ==========================================
# 🧠 計算・分析関数群
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

def fetch_and_analyze(item):
    name, code = item
    if code == "" or pd.isna(code): return None
    try:
        stock_data = yf.Ticker(code).history(period="3mo")
        if stock_data.empty: return None
        current_price = stock_data['Close'].iloc[-1]
        rsi_series = calculate_rsi(stock_data['Close'])
        current_rsi = rsi_series.iloc[-1]
        x = np.arange(len(stock_data))
        slope, _ = np.polyfit(x, stock_data['Close'], 1)
        return {
            "コード": code,
            "銘柄名": name,
            "現在値": current_price,
            "表示価格": f"{current_price:,.2f}",
            "RSI": f"{current_rsi:.1f}",
            "判定コメント": ("上昇" if slope > 0 else "") + (", RSI安" if current_rsi <= 30 else ""),
            "raw_rsi": current_rsi,
            "raw_slope": slope
        }
    except:
        return None

def fetch_name(code):
    try:
        t = yf.Ticker(code)
        return t.info.get('shortName') or t.info.get('longName') or code
    except:
        return code

def play_text_to_speech(text):
    try:
        clean_text = text.replace("*", "").replace("#", "").replace(":", "、").replace("\n", "。")
        tts = gTTS(text=clean_text, lang='ja')
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        st.audio(audio_bytes, format='audio/mp3', autoplay=True)
    except Exception as e:
        st.warning(f"読み上げエラー: {e}")

def check_track_record(row):
    try:
        code = row['コード']
        start_price = float(row['登録時株価'])
        reg_date = row['登録日']
        df = yf.Ticker(code).history(start=str(reg_date))
        if df.empty: return None
        current_price = df['Close'].iloc[-1]
        high_price = df['High'].max()
        diff_percent = ((current_price - start_price) / start_price) * 100
        high_percent = ((high_price - start_price) / start_price) * 100
        return {
            "登録日": reg_date,
            "銘柄名": row['銘柄名'],
            "コード": code,
            "登録値": f"{start_price:,.0f}",
            "現在値": f"{current_price:,.0f}",
            "結果": f"{diff_percent:+.1f}%",
            "期間高値": f"{high_price:,.0f} (+{high_percent:.1f}%)",
            "raw_diff": diff_percent
        }
    except:
        return None

def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8-sig') # 文字化け防止

# ==========================================
# 📱 画面表示
# ==========================================
clean_old_history()

st.subheader("📊 トレーダーズ・ステーション Pro (CSV Export 📥)")

with st.sidebar:
    st.header("🔍 爆速スキャナー")
    use_rsi = st.checkbox("RSIで絞り込む", value=True)
    rsi_threshold = st.slider("RSIがこれ以下", 10, 50, 30)
    use_trend = st.checkbox("上昇トレンドのみ", value=False)
    if st.button("リストをスキャン開始 🚀", type="primary"):
        st.session_state.run_scan = True

tab1, tab2 = st.tabs(["📈 本日の分析・登録", "🕵️ 過去の検証・答え合わせ"])

# --- タブ1: 分析 ---
with tab1:
    area = st.radio("エリア選択", ["🇯🇵 日本", "🇺🇸 米国", "🌏 世界・資源", "💱 FX"], horizontal=True)
    meigara_list = {}

    if area == "🇯🇵 日本":
        cat = st.radio("カテゴリー", ["📝 マイ登録銘柄 (編集可)", "💰 値がさ", "👛 手頃", "📉 低位・ボロ株"], horizontal=True)
        if cat == "📝 マイ登録銘柄 (編集可)":
            st.info("👇 コード入力 → 名前取得 → スキャン → 良ければ保存！")
            edited_df = st.data_editor(st.session_state.my_stock_list, num_rows="dynamic", column_order=["コード", "銘柄名"], key="editor", use_container_width=True)
            st.session_state.my_stock_list = edited_df
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("🔄 名前自動取得"):
                    with st.spinner("取得中..."):
                        codes = edited_df["コード"].tolist()
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            names = list(executor.map(fetch_name, codes))
                        st.session_state.my_stock_list["銘柄名"] = names
                        st.rerun()
            with c2:
                if st.button("💾 リスト一時保存"): st.success("保存完了！")
            with c3:
                if st.button("🗑️ 全消去"):
                    st.session_state.my_stock_list = pd.DataFrame({"コード": [], "銘柄名": []})
                    st.rerun()
            meigara_list = dict(zip(edited_df["銘柄名"], edited_df["コード"]))
        elif cat == "💰 値がさ": meigara_list = {"🇯🇵 ファストリ": "9983.T", "🇯🇵 東エレク": "8035.T", "🇯🇵 キーエンス": "6861.T"}
        elif cat == "👛 手頃": meigara_list = {"🇯🇵 ENEOS": "5020.T", "🇯🇵 楽天G": "4755.T", "🇯🇵 イオン": "8267.T"}
        else: meigara_list = {"🇯🇵 日産": "7201.T", "🇯🇵 セブン銀": "8410.T", "🇯🇵 マツダ": "7261.T"}
    elif area == "🇺🇸 米国": meigara_list = {"🇺🇸 NVDA": "NVDA", "🇺🇸 TSLA": "TSLA", "🇺🇸 AAPL": "AAPL"}
    elif area == "🌏 世界・資源": meigara_list = {"🥇 金": "GLD", "🪙 BTC": "BTC-USD"}
    else: meigara_list = {"🇺🇸/🇯🇵 ドル円": "USDJPY=X"}

    if st.session_state.get("run_scan", False):
        target_items = list(meigara_list.items())
        hit_data = []
        target_items = [item for item in target_items if item[1] != "" and not pd.isna(item[1])]
        if len(target_items) == 0: st.warning("リストが空です！")
        else:
            with st.spinner(f"🚀 スキャン中... ({len(target_items)}件)"):
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    results = list(executor.map(fetch_and_analyze, target_items))
                for res in results:
                    if res is None: continue
                    is_hit = True
                    if use_rsi and res['raw_rsi'] > rsi_threshold: is_hit = False
                    if use_trend and res['raw_slope'] <= 0: is_hit = False
                    if is_hit: hit_data.append(res)
            if hit_data:
                st.session_state.scan_results = pd.DataFrame(hit_data).drop(columns=['raw_rsi', 'raw_slope', '現在値'])
                st.session_state.raw_scan_results = hit_data
                st.success(f"💎 {len(hit_data)}件ヒット！")
            else:
                st.session_state.scan_results = pd.DataFrame()
                st.warning("条件に合う銘柄なし")
        st.session_state.run_scan = False

    if st.session_state.scan_results is not None and not st.session_state.scan_results.empty:
        event = st.dataframe(st.session_state.scan_results, selection_mode="multi-row", on_select="rerun", hide_index=True, use_container_width=True, key="scan_table")
        
        # ★★★ CSVダウンロードボタン (スキャン結果) ★★★
        csv = convert_df_to_csv(st.session_state.scan_results)
        st.download_button("📥 スキャン結果をCSVでダウンロード", data=csv, file_name="scan_results.csv", mime="text/csv")

        st.markdown("##### 👇 チェックした銘柄を「検証リスト」に保存")
        if st.button("💾 チェックした銘柄を追跡開始 (1週間)"):
            if len(event.selection.rows) > 0:
                selected_indices = event.selection.rows
                history_df = load_history()
                new_entries = []
                today = datetime.date.today()
                for idx in selected_indices:
                    item = st.session_state.raw_scan_results[idx]
                    new_entries.append({"登録日": today, "銘柄名": item['銘柄名'], "コード": item['コード'], "登録時株価": item['現在値']})
                if new_entries:
                    new_df = pd.DataFrame(new_entries)
                    history_df = pd.concat([history_df, new_df], ignore_index=True)
                    save_history(history_df)
                    st.success(f"{len(new_entries)}件を検証リストに追加しました！")
            else:
                st.warning("表のチェックボックスで銘柄を選んでください。")

# --- タブ2: 検証 ---
with tab2:
    st.header("🕵️ 答え合わせ（過去1週間）")
    history_df = load_history()
    
    if history_df.empty:
        st.write("データなし。タブ1で登録してください。")
    else:
        # ★★★ CSVダウンロードボタン (検証履歴) ★★★
        csv_hist = convert_df_to_csv(history_df)
        col_h1, col_h2 = st.columns([3, 1])
        with col_h2:
            st.download_button("📥 検証データをCSV保存", data=csv_hist, file_name="my_track_record.csv", mime="text/csv")

        if st.button("🔄 最新価格で答え合わせを実行"):
            with st.spinner("過去のデータを追跡中..."):
                records = history_df.to_dict('records')
                results = []
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    results = list(executor.map(check_track_record, records))
                final_results = [r for r in results if r is not None]
                if final_results:
                    res_df = pd.DataFrame(final_results)
                    def highlight_result(val):
                        color = 'red' if '+' in val else 'blue'
                        return f'color: {color}; font-weight: bold'
                    st.dataframe(res_df.style.map(highlight_result, subset=['結果', '期間高値']), hide_index=True, use_container_width=True)
                    
                    # 結果が出た後のデータもDLできるようにする
                    csv_res = convert_df_to_csv(res_df)
                    st.download_button("📥 答え合わせ結果をDL", data=csv_res, file_name="verification_result.csv", mime="text/csv")

                else: st.error("データ取得エラー")
        else:
             st.dataframe(history_df, hide_index=True, use_container_width=True)