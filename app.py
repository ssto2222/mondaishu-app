import streamlit as st
import json
import glob
import os
import pandas as pd
from datetime import datetime
from supabase import create_client

st.set_page_config(page_title="社労士合格アプリ Pro v2", layout="wide")

# =========================
# Supabase接続
# =========================
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("Supabase設定エラー")
    st.stop()

# =========================
# 問題読み込み
# =========================
@st.cache_data
def load_all_questions():
    all_data = {}
    json_files = glob.glob("*.json")
    for file_path in json_files:
        subject_name = os.path.splitext(os.path.basename(file_path))[0]
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                questions = json.load(f)
                if isinstance(questions, list): all_data[subject_name] = questions
        except: pass
    return all_data

questions_dict = load_all_questions()

# =========================
# セッション初期化
# =========================
if "index" not in st.session_state: st.session_state.index = 0
if "answered" not in st.session_state: st.session_state.answered = False
if "wrong_data" not in st.session_state: st.session_state.wrong_data = {} # {id: {miss: X, streak: Y}}
if "current_category" not in st.session_state: st.session_state.current_category = ""
if "all_progress" not in st.session_state: st.session_state.all_progress = {}
if "db_synced" not in st.session_state: st.session_state.db_synced = False

# =========================
# 同期関数 (履歴情報を含む)
# =========================
def sync_user_data(user_id, category):
    try:
        # 1. 苦手問題の詳細データ（ミス回数、連続正解数）を取得
        res_w = supabase.table("wrong_questions").select("question_id, miss_count, correct_streak").eq("user_id", user_id).execute()
        st.session_state.wrong_data = {
            item["question_id"]: {"miss": item["miss_count"], "streak": item["correct_streak"]} 
            for item in res_w.data
        }
        
        # 2. 進捗取得
        res_p = supabase.table("user_progress").select("category, last_index").eq("user_id", user_id).execute()
        prog_map = {item["category"]: item["last_index"] for item in res_p.data}
        st.session_state.all_progress = prog_map
        st.session_state.index = prog_map.get(category, 0)
        st.session_state.db_synced = True
    except:
        st.warning("同期エラー")

# =========================
# サイドバー
# =========================
with st.sidebar:
    st.title("📈 学習履歴")
    user_id = st.text_input("ユーザーID")
    category = st.selectbox("科目", sorted(list(questions_dict.keys())))

    if category != st.session_state.current_category:
        st.session_state.current_category = category
        st.session_state.db_synced = False
        st.session_state.answered = False
        if user_id: sync_user_data(user_id, category)
        st.rerun()

    if user_id and not st.session_state.db_synced:
        sync_user_data(user_id, category)

    mode = st.radio("モード", ["通常学習", "徹底復習 🔥"])
    st.caption("※徹底復習は3回連続正解でリストから消えます")

# =========================
# 問題抽出
# =========================
all_target = questions_dict.get(category, [])
if mode == "徹底復習 🔥":
    target = [q for q in all_target if q["id"] in st.session_state.wrong_data]
else:
    target = all_target

if not target:
    st.success("対象問題なし"); st.stop()

if st.session_state.index >= len(target): st.session_state.index = 0
q = target[st.session_state.index]

# =========================
# メイン画面
# =========================
st.title(f"📖 {category}")
# 苦手情報の表示
if q["id"] in st.session_state.wrong_data:
    info = st.session_state.wrong_data[q["id"]]
    st.warning(f"⚠️ 過去に {info['miss']} 回ミス / 現在 {info['streak']} 回連続正解中")

st.progress(min((st.session_state.index + 1) / len(target), 1.0))
st.markdown(f"### {q['q']}")

col1, col2 = st.columns(2)
user_ans = None
if not st.session_state.answered:
    if col1.button("○ 正解", use_container_width=True): user_ans, st.session_state.answered = "○", True
    if col2.button("× 不正解", use_container_width=True): user_ans, st.session_state.answered = "×", True

# =========================
# 判定ロジック (履歴保存)
# =========================
if st.session_state.answered:
    correct = (user_ans == q["a"]) if user_ans else (st.session_state.last_ans == q["a"])
    
    if user_id:
        # 現在のステータスを取得
        current = st.session_state.wrong_data.get(q["id"], {"miss": 0, "streak": 0})
        
        if correct:
            st.success("✨ 正解！")
            new_streak = current["streak"] + 1
            if new_streak >= 3: # 3回連続正解でリストから削除
                supabase.table("wrong_questions").delete().eq("user_id", user_id).eq("question_id", q["id"]).execute()
                if q["id"] in st.session_state.wrong_data: del st.session_state.wrong_data[q["id"]]
                st.balloons()
                st.info("マスターしました！リストから削除します。")
            else:
                supabase.table("wrong_questions").upsert({
                    "user_id": user_id, "question_id": q["id"], "category": category,
                    "miss_count": current["miss"], "correct_streak": new_streak
                }).execute()
                st.session_state.wrong_data[q["id"]] = {"miss": current["miss"], "streak": new_streak}
        else:
            st.error(f"不正解... 正解は {q['a']}")
            new_miss = current["miss"] + 1
            supabase.table("wrong_questions").upsert({
                "user_id": user_id, "question_id": q["id"], "category": category,
                "miss_count": new_miss, "correct_streak": 0 # ストリークはリセット
            }).execute()
            st.session_state.wrong_data[q["id"]] = {"miss": new_miss, "streak": 0}

    st.info(f"💡 解説: {q['tips']}")

    if st.button("次へ ➡️", use_container_width=True):
        st.session_state.index += 1
        st.session_state.answered = False
        if mode == "通常学習" and user_id:
            supabase.table("user_progress").upsert({"user_id": user_id, "category": category, "last_index": st.session_state.index}).execute()
        st.rerun()