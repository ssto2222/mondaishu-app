import streamlit as st
from st_supabase_connection import SupabaseConnection
import json
import random

# --- 1. ページ設定 & 接続 ---
st.set_page_config(page_title="社労士合格V2 - クラウド同期版", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)

# --- 2. クラウド同期ロジック ---
def load_user_progress(uid):
    """Supabaseから苦手問題IDセットを読み込み"""
    try:
        res = conn.table("study_progress").select("wrong_questions").eq("user_id", uid).execute()
        if res.data and res.data[0]["wrong_questions"]:
            return set(res.data[0]["wrong_questions"])
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
    return set()

def save_user_progress(uid, wrong_set):
    """Supabaseへ苦手問題IDリストを保存"""
    try:
        data = {"user_id": uid, "wrong_questions": list(wrong_set)}
        conn.table("study_progress").upsert(data).execute()
    except Exception as e:
        st.warning(f"同期失敗: {e}")

# --- 3. 問題データ (JSON構造) ---
# ※実際には questions.json から読み込むコードが望ましいですが、ここでは例示用に定義
def get_questions():
    # ここに以前作成した「労災・雇用・健保」のフルJSON（各150問）を読み込みます
    # 今回はサンプルとして構造のみ記述
    try:
        with open("questions.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {
            "労災保険法_基本": [{"id": 201, "q": "保険者は政府である", "a": "○", "tips": "..."}],
            "雇用保険法_基本": [{"id": 401, "q": "週20時間以上で加入", "a": "○", "tips": "..."}]
        }

# --- 4. セッション状態の初期化 ---
if "user_id" not in st.session_state:
    st.session_state.user_id = ""
if "wrong_ids" not in st.session_state:
    st.session_state.wrong_ids = set()
if "current_q" not in st.session_state:
    st.session_state.current_q = None

# --- 5. サイドバー (ユーザー設定 & 科目選択) ---
with st.sidebar:
    st.header("👤 ユーザー設定")
    uid_input = st.text_input("ユーザーIDを入力（同期用）", value=st.session_state.user_id)
    
    if uid_input and uid_input != st.session_state.user_id:
        st.session_state.user_id = uid_input
        st.session_state.wrong_ids = load_user_progress(uid_input)
        st.success("同期しました")

    st.divider()
    
    questions_data = get_questions()
    category = st.selectbox("科目を選択", list(questions_data.keys()))
    mode = st.radio("モード選択", ["通常モード", "苦手克服モード（クラウド同期）"])

    if st.button("履歴をリセット"):
        st.session_state.wrong_ids = set()
        save_user_progress(st.session_state.user_id, set())
        st.rerun()

# --- 6. メインロジック ---
st.title(f"📖 {category}")
st.caption(f"現在の苦手問題数: {len(st.session_state.wrong_ids)}問")

# 出題対象の決定
target_questions = questions_data[category]
if mode == "苦手克服モード（クラウド同期）":
    target_questions = [q for q in target_questions if q["id"] in st.session_state.wrong_ids]

if not target_questions:
    st.info("対象の問題がありません。")
else:
    # 次の問題へボタン、または初回起動時
    if st.button("次の問題を表示") or st.session_state.current_q is None:
        st.session_state.current_q = random.choice(target_questions)
        st.session_state.answered = False

    q = st.session_state.current_q

    # 問題表示
    st.subheader(f"問題 ID: {q['id']}")
    st.write(q["q"])

    col1, col2 = st.columns(2)
    with col1:
        if st.button("○"):
            st.session_state.user_ans = "○"
            st.session_state.answered = True
    with col2:
        if st.button("×"):
            st.session_state.user_ans = "×"
            st.session_state.answered = True

    # 回答判定
    if st.session_state.get("answered"):
        if st.session_state.user_ans == q["a"]:
            st.success("正解！")
            # 正解したら苦手リストから削除
            if q["id"] in st.session_state.wrong_ids:
                st.session_state.wrong_ids.remove(q["id"])
                save_user_progress(st.session_state.user_id, st.session_state.wrong_ids)
        else:
            st.error(f"不正解...（正解は {q['a']}）")
            # 間違えたら苦手リストに追加
            if q["id"] not in st.session_state.wrong_ids:
                st.session_state.wrong_ids.add(q["id"])
                save_user_progress(st.session_state.user_id, st.session_state.wrong_ids)
        
        with st.expander("解説を見る"):
            st.info(q["tips"])

# --- 7. 進捗状況の可視化 ---
st.divider()
progress_val = len(st.session_state.wrong_ids)
st.progress(min(progress_val / 150, 1.0)) # 各科目150問想定