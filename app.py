import streamlit as st
import json
import glob
import os
import pandas as pd
from datetime import datetime, date
from supabase import create_client

# ページ設定
st.set_page_config(page_title="社労士合格 Pro v3.6", layout="wide")

# =========================
# Supabase接続
# =========================
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("Supabase設定エラー。Secretsを確認してください。")
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
                if isinstance(questions, list): 
                    all_data[subject_name] = questions
        except:
            continue
    return all_data

questions_dict = load_all_questions()

# =========================
# セッション状態の初期化
# =========================
if "index" not in st.session_state: st.session_state.index = 0
if "answered" not in st.session_state: st.session_state.answered = False
if "last_result" not in st.session_state: st.session_state.last_result = None
if "wrong_data" not in st.session_state: st.session_state.wrong_data = {}
if "current_category" not in st.session_state: st.session_state.current_category = ""
if "db_synced" not in st.session_state: st.session_state.db_synced = False

# =========================
# DB操作関数
# =========================
def log_study_count(user_id):
    if user_id:
        try:
            today = date.today().isoformat()
            res = supabase.table("daily_stats").select("count").eq("user_id", user_id).eq("study_date", today).execute()
            new_count = (res.data[0]["count"] + 1) if res.data else 1
            supabase.table("daily_stats").upsert({"user_id": user_id, "study_date": today, "count": new_count}).execute()
        except: pass

def sync_user_data(user_id, category):
    try:
        # 間違えた問題リストを取得
        res_w = supabase.table("wrong_questions").select("question_id, category, miss_count, correct_streak").eq("user_id", user_id).execute()
        st.session_state.wrong_data = {
            str(item["question_id"]): {
                "miss": item["miss_count"], 
                "streak": item["correct_streak"],
                "category": item["category"]
            } for item in res_w.data
        }
        # 進捗取得
        res_p = supabase.table("user_progress").select("category, last_index").eq("user_id", user_id).execute()
        prog_map = {item["category"]: item["last_index"] for item in res_p.data}
        
        if category == "🔥 全科目から復習":
            st.session_state.index = 0
        else:
            st.session_state.index = prog_map.get(category, 0)
        st.session_state.db_synced = True
    except: pass

# =========================
# サイドバー
# =========================
with st.sidebar:
    st.title("🚀 学習管理")
    exam_date = date(2026, 8, 23)
    days_left = (exam_date - date.today()).days
    st.metric("本試験まで", f"あと {days_left} 日")
    st.divider()

    user_id = st.text_input("ユーザーID", placeholder="yamada_01")
    cat_options = ["🔥 全科目から復習"] + sorted(list(questions_dict.keys()))
    category = st.selectbox("科目を選択", cat_options)

    if category != st.session_state.current_category:
        st.session_state.current_category = category
        st.session_state.db_synced = False
        st.session_state.answered = False
        st.session_state.index = 0
        if user_id: sync_user_data(user_id, category)
        st.rerun()

    if user_id and not st.session_state.db_synced:
        sync_user_data(user_id, category)

    mode = st.radio("学習モード", ["通常学習", "徹底復習 🔥"])
    
    # --- 学習進捗データの表示 (戻した部分) ---
    if user_id:
        st.divider()
        st.subheader("📊 今週の学習状況")
        try:
            res_stats = supabase.table("daily_stats").select("study_date, count").eq("user_id", user_id).order("study_date").execute()
            if res_stats.data:
                df = pd.DataFrame(res_stats.data)
                df['study_date'] = pd.to_datetime(df['study_date']).dt.date
                df = df.set_index("study_date")
                st.bar_chart(df["count"])
            else:
                st.caption("学習データがまだありません。")
        except:
            st.caption("統計データの読み込みに失敗しました。")

# =========================
# 問題抽出ロジック
# =========================
target = []
all_combined = []
for cat, qs in questions_dict.items():
    for q_item in qs:
        q_item["_origin_cat"] = cat
        all_combined.append(q_item)

if category == "🔥 全科目から復習":
    target = [q for q in all_combined if str(q["id"]) in st.session_state.wrong_data]
else:
    all_target = questions_dict.get(category, [])
    if mode == "徹底復習 🔥":
        target = [q for q in all_target if str(q["id"]) in st.session_state.wrong_data]
    else:
        target = all_target

if not target:
    st.success("🎉 対象の問題はありません！")
    st.stop()

if st.session_state.index >= len(target): st.session_state.index = 0
q = target[st.session_state.index]

# =========================
# メイン画面
# =========================
display_cat = q.get("_origin_cat", category)
st.title(f"📖 {display_cat}")

# --- 学習履歴ステータスの表示 ---
q_id_str = str(q["id"])
history = st.session_state.wrong_data.get(q_id_str)

col_stat1, col_stat2 = st.columns([1, 1])
with col_stat1:
    # 履歴がない、もしくはミスも連続正解も0の場合は「初回」
    if not history or (history.get("miss", 0) == 0 and history.get("streak", 0) == 0):
        st.info("🆕 **初回挑戦**")
    else:
        st.warning(f"⚠️ 累計ミス: **{history['miss']}** 回")
with col_stat2:
    if history and history.get("streak", 0) > 0:
        st.success(f"🔥 連続正解: **{history['streak']}**")

st.markdown(f"### Q{st.session_state.index + 1}. {q['q']}")
st.divider()

# --- 判定処理 ---
user_choice = None
status_action = None 

if not st.session_state.answered:
    c1, c2, c3 = st.columns(3)
    if c1.button("○ 正解", use_container_width=True, type="primary"): 
        user_choice = "○"
        status_action = "correct"
    if c2.button("× 不正解", use_container_width=True, type="secondary"): 
        user_choice = "×"
        status_action = "wrong"
    if c3.button("△ あやふや", use_container_width=True): 
        user_choice = "uncertain"
        status_action = "uncertain"

    if status_action:
        st.session_state.answered = True
        
        if status_action == "uncertain":
            is_correct = False
            st.session_state.last_result = "uncertain"
        else:
            is_correct = (user_choice == q["a"])
            st.session_state.last_result = "correct" if is_correct else "wrong"
        
        if user_id:
            curr = st.session_state.wrong_data.get(q_id_str, {"miss": 0, "streak": 0})
            target_cat = q.get("_origin_cat", category)
            
            if is_correct:
                new_streak = curr["streak"] + 1
                if new_streak >= 3:
                    supabase.table("wrong_questions").delete().eq("user_id", user_id).eq("question_id", q_id_str).execute()
                    if q_id_str in st.session_state.wrong_data: del st.session_state.wrong_data[q_id_str]
                else:
                    supabase.table("wrong_questions").upsert({"user_id": user_id, "question_id": q_id_str, "category": target_cat, "miss_count": curr["miss"], "correct_streak": new_streak}).execute()
                    st.session_state.wrong_data[q_id_str] = {"miss": curr["miss"], "streak": new_streak}
            else:
                # 不正解または△の場合はミスとしてカウント
                new_miss = curr["miss"] + 1
                supabase.table("wrong_questions").upsert({"user_id": user_id, "question_id": q_id_str, "category": target_cat, "miss_count": new_miss, "correct_streak": 0}).execute()
                st.session_state.wrong_data[q_id_str] = {"miss": new_miss, "streak": 0}
        st.rerun()

# --- 結果表示 ---
if st.session_state.answered:
    res = st.session_state.last_result
    if res == "correct":
        st.success("✨ **正解です！**")
    elif res == "uncertain":
        st.warning(f"🤔 **あやふや（正解は {q['a']}）** \n\n 記憶が定着するまで繰り返し復習しましょう。")
    else:
        st.error(f"❌ **残念！ 正解は 【 {q['a']} 】**")
    
    st.info(f"💡 **解説**\n\n{q['tips']}")

    if st.button("次の問題へ ➡️", use_container_width=True, type="primary"):
        if user_id:
            log_study_count(user_id)
            if category != "🔥 全科目から復習" and mode == "通常学習":
                supabase.table("user_progress").upsert({"user_id": user_id, "category": category, "last_index": st.session_state.index + 1}).execute()
        
        st.session_state.index += 1
        st.session_state.answered = False
        st.session_state.last_result = None
        st.rerun()
