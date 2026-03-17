import streamlit as st
import json
import glob
import os
import pandas as pd
from datetime import datetime, date
from supabase import create_client

# ページ設定
st.set_page_config(page_title="社労士合格 Pro v3.2", layout="wide")

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
                if isinstance(questions, list): all_data[subject_name] = questions
        except: pass
    return all_data

questions_dict = load_all_questions()

# =========================
# セッション状態の初期化
# =========================
if "index" not in st.session_state: st.session_state.index = 0
if "answered" not in st.session_state: st.session_state.answered = False
if "last_result" not in st.session_state: st.session_state.last_result = None # 判定結果保持用
if "wrong_data" not in st.session_state: st.session_state.wrong_data = {}
if "current_category" not in st.session_state: st.session_state.current_category = ""
if "all_progress" not in st.session_state: st.session_state.all_progress = {}
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
        res_w = supabase.table("wrong_questions").select("question_id, miss_count, correct_streak").eq("user_id", user_id).execute()
        st.session_state.wrong_data = {item["question_id"]: {"miss": item["miss_count"], "streak": item["correct_streak"]} for item in res_w.data}
        res_p = supabase.table("user_progress").select("category, last_index").eq("user_id", user_id).execute()
        prog_map = {item["category"]: item["last_index"] for item in res_p.data}
        st.session_state.all_progress = prog_map
        st.session_state.index = prog_map.get(category, 0)
        st.session_state.db_synced = True
    except: pass

# =========================
# サイドバー
# =========================
with st.sidebar:
    st.title("🚀 学習管理")
    
    # --- 試験日カウントダウン ---
    exam_date = date(2026, 8, 23)
    days_left = (exam_date - date.today()).days
    st.metric("本試験まで", f"あと {days_left} 日")
    st.divider()

    user_id = st.text_input("ユーザーID", placeholder="yamada_01")
    category = st.selectbox("科目を選択", sorted(list(questions_dict.keys())))

    if category != st.session_state.current_category:
        st.session_state.current_category = category
        st.session_state.db_synced = False
        st.session_state.answered = False
        st.session_state.last_result = None
        if user_id: sync_user_data(user_id, category)
        st.rerun()

    if user_id and not st.session_state.db_synced:
        sync_user_data(user_id, category)

    mode = st.radio("学習モード", ["通常学習", "徹底復習 🔥"])
    
    if user_id:
        st.divider()
        try:
            res_stats = supabase.table("daily_stats").select("study_date, count").eq("user_id", user_id).order("study_date").execute()
            if res_stats.data:
                df = pd.DataFrame(res_stats.data).set_index("study_date")
                st.bar_chart(df["count"])
        except: pass

# =========================
# 問題抽出
# =========================
all_target = questions_dict.get(category, [])
target = [q for q in all_target if q["id"] in st.session_state.wrong_data] if mode == "徹底復習 🔥" else all_target

if not target:
    st.success("🎉 対象の問題はありません！"); st.stop()

if st.session_state.index >= len(target): st.session_state.index = 0
q = target[st.session_state.index]

# =========================
# メイン画面
# =========================
st.title(f"📖 {category}")

miss_count = st.session_state.wrong_data.get(q["id"], {}).get("miss", 0)
streak_count = st.session_state.wrong_data.get(q["id"], {}).get("streak", 0)

if miss_count >= 5:
    st.error(f"🚨 **【最重要復習】累計ミス {miss_count}回！**")
    st.markdown("""<div style="background-color: #ffebee; padding: 20px; border-radius: 10px; border-left: 5px solid #ff1744;">""", unsafe_allow_html=True)
elif miss_count >= 1:
    st.warning(f"⚠️ 累計ミス {miss_count}回 / 連続正解 {streak_count}回")

st.markdown(f"### Q{st.session_state.index + 1}. {q['q']}")
if miss_count >= 5: st.markdown("</div>", unsafe_allow_html=True)

st.divider()

# --- 判定処理 ---
col1, col2 = st.columns(2)
user_choice = None

if not st.session_state.answered:
    if col1.button("○ 正解", use_container_width=True): user_choice = "○"
    if col2.button("× 不正解", use_container_width=True): user_choice = "×"

    if user_choice:
        st.session_state.answered = True
        is_correct = (user_choice == q["a"])
        st.session_state.last_result = is_correct # 結果をセッションに固定
        
        if user_id:
            curr = st.session_state.wrong_data.get(q["id"], {"miss": 0, "streak": 0})
            if is_correct:
                new_streak = curr["streak"] + 1
                if new_streak >= 3:
                    supabase.table("wrong_questions").delete().eq("user_id", user_id).eq("question_id", q["id"]).execute()
                    if q["id"] in st.session_state.wrong_data: del st.session_state.wrong_data[q["id"]]
                else:
                    supabase.table("wrong_questions").upsert({"user_id": user_id, "question_id": q["id"], "category": category, "miss_count": curr["miss"], "correct_streak": new_streak}).execute()
                    st.session_state.wrong_data[q["id"]] = {"miss": curr["miss"], "streak": new_streak}
            else:
                new_miss = curr["miss"] + 1
                supabase.table("wrong_questions").upsert({"user_id": user_id, "question_id": q["id"], "category": category, "miss_count": new_miss, "correct_streak": 0}).execute()
                st.session_state.wrong_data[q["id"]] = {"miss": new_miss, "streak": 0}
        st.rerun()

# --- 判定結果の表示（再描画されても維持される） ---
if st.session_state.answered:
    if st.session_state.last_result:
        st.success("✨ 正解です！")
    else:
        st.error(f"残念！ 正解は 【 {q['a']} 】")
    
    st.info(f"💡 **解説**\n\n{q['tips']}")

    if st.button("次の問題へ ➡️", use_container_width=True):
        if user_id:
            log_study_count(user_id)
            if mode == "通常学習":
                supabase.table("user_progress").upsert({"user_id": user_id, "category": category, "last_index": st.session_state.index + 1}).execute()
        
        # 状態をリセットして次へ
        st.session_state.index += 1
        st.session_state.answered = False
        st.session_state.last_result = None
        st.rerun()