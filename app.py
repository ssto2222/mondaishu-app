import streamlit as st
from st_supabase_connection import SupabaseConnection
import json
import random

# --- 1. ページ設定 & 接続 ---
st.set_page_config(page_title="社労士合格V2 - 進捗完全同期版", layout="centered")
conn = st.connection("supabase", type=SupabaseConnection)

# --- 2. クラウド同期ロジック ---
def load_all_progress(uid):
    """Supabaseからすべての進捗状況を読み込み"""
    try:
        res = conn.table("study_progress").select("*").eq("user_id", uid).execute()
        if res.data:
            d = res.data[0]
            return {
                "wrong_ids": set(d.get("wrong_questions", [])),
                "category": d.get("current_category"),
                "mode": d.get("current_mode"),
                "index": d.get("current_index", 0)
            }
    except Exception as e:
        st.error(f"ロードエラー: {e}")
    return {"wrong_ids": set(), "category": None, "mode": None, "index": 0}

def save_all_progress(uid, wrong_set, cat, mode, idx):
    """Supabaseへすべての進捗を保存"""
    if not uid: return
    try:
        data = {
            "user_id": uid,
            "wrong_questions": list(wrong_set),
            "current_category": cat,
            "current_mode": mode,
            "current_index": idx
        }
        conn.table("study_progress").upsert(data).execute()
    except Exception as e:
        st.warning(f"同期失敗: {e}")

# --- 3. 問題データ読み込み ---
def get_questions():
    try:
        with open("questions.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"データなし": [{"id": 0, "q": "questions.jsonが見つかりません", "a": "×", "tips": ""}]}

# --- 4. セッション状態の初期化 ---
if "user_id" not in st.session_state:
    st.session_state.user_id = ""
if "wrong_ids" not in st.session_state:
    st.session_state.wrong_ids = set()
if "q_index" not in st.session_state:
    st.session_state.q_index = 0
if "answered" not in st.session_state:
    st.session_state.answered = False

# --- 5. サイドバー ---
with st.sidebar:
    st.header("👤 ユーザー設定")
    uid_input = st.text_input("ユーザーID（同期用）", value=st.session_state.user_id)
    
    if uid_input and uid_input != st.session_state.user_id:
        st.session_state.user_id = uid_input
        progress = load_all_progress(uid_input)
        st.session_state.wrong_ids = progress["wrong_ids"]
        # 復元ボタンの表示フラグ
        st.session_state.restored_data = progress
        st.success("同期完了")

    st.divider()
    
    questions_data = get_questions()
    
    # 復元データがある場合、初期値を設定
    default_cat = list(questions_data.keys())[0]
    default_mode = "通常モード"
    if "restored_data" in st.session_state and st.session_state.restored_data["category"]:
        if st.button("前回の続きから再開"):
            default_cat = st.session_state.restored_data["category"]
            default_mode = st.session_state.restored_data["mode"]
            st.session_state.q_index = st.session_state.restored_data["index"]
            st.rerun()

    category = st.selectbox("科目を選択", list(questions_data.keys()), index=list(questions_data.keys()).index(default_cat) if default_cat in questions_data else 0)
    mode = st.radio("モード選択", ["通常モード", "苦手克服モード"], index=0 if default_mode == "通常モード" else 1)

# --- 6. メインロジック ---
st.title(f"📖 {category}")

target_questions = questions_data[category]
if mode == "苦手克服モード":
    target_questions = [q for q in target_questions if q["id"] in st.session_state.wrong_ids]

if not target_questions:
    st.info("対象の問題がありません。")
else:
    # インデックスが範囲外にならないよう調整
    if st.session_state.q_index >= len(target_questions):
        st.session_state.q_index = 0

    q = target_questions[st.session_state.q_index]

    st.subheader(f"問題 {st.session_state.q_index + 1} / {len(target_questions)} (ID: {q['id']})")
    st.write(q["q"])

    col1, col2 = st.columns(2)
    with col1:
        if st.button("○", use_container_width=True):
            st.session_state.user_ans = "○"
            st.session_state.answered = True
    with col2:
        if st.button("×", use_container_width=True):
            st.session_state.user_ans = "×"
            st.session_state.answered = True

    if st.session_state.answered:
        if st.session_state.user_ans == q["a"]:
            st.success("正解！")
            if q["id"] in st.session_state.wrong_ids:
                st.session_state.wrong_ids.remove(q["id"])
        else:
            st.error(f"不正解...（正解は {q['a']}）")
            st.session_state.wrong_ids.add(q["id"])
        
        with st.expander("解説を見る"):
            st.info(q["tips"])
        
        if st.button("次の問題へ"):
            st.session_state.q_index += 1
            st.session_state.answered = False
            # ここで全ての進捗をクラウドに保存
            save_all_progress(
                st.session_state.user_id, 
                st.session_state.wrong_ids, 
                category, 
                mode, 
                st.session_state.q_index
            )
            st.rerun()

# --- 7. 進捗バー ---
st.divider()
total_q = len(questions_data[category])
st.write(f"全体の進捗（苦手克服状況）: {total_q - len([qi for qi in target_questions if qi['id'] in st.session_state.wrong_ids])} / {total_q}")
st.progress(st.session_state.q_index / len(target_questions) if target_questions else 0)