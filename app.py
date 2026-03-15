import streamlit as st
import json
import glob
import os
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client

st.set_page_config(page_title="社労士合格アプリ Pro", layout="wide")

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
# セッション状態
# =========================
for key in ["index", "answered", "last_ans", "current_category", "db_synced"]:
    if key not in st.session_state: st.session_state[key] = 0 if key == "index" else (False if "synced" in key or "answered" in key else "")

if "wrong_ids" not in st.session_state: st.session_state.wrong_ids = set()
if "all_progress" not in st.session_state: st.session_state.all_progress = {}

# =========================
# 学習ログ記録関数 (グラフ用)
# =========================
def log_study_count(user_id):
    if user_id:
        try:
            today = datetime.now().date().isoformat()
            # 既存のカウントを取得して+1 (upsert)
            res = supabase.table("daily_stats").select("count").eq("user_id", user_id).eq("study_date", today).execute()
            new_count = (res.data[0]["count"] + 1) if res.data else 1
            supabase.table("daily_stats").upsert({"user_id": user_id, "study_date": today, "count": new_count}).execute()
        except: pass

# =========================
# サイドバー & ダッシュボード
# =========================
with st.sidebar:
    st.title("🚀 合格ロードマップ")
    user_id = st.text_input("ユーザーID", placeholder="yamada_01")
    
    category = st.selectbox("科目を選択", sorted(list(questions_dict.keys())))
    
    # 科目変更時のリセット
    if category != st.session_state.current_category:
        st.session_state.current_category = category
        st.session_state.db_synced = False
        st.rerun()

    # 同期ロジック
    if user_id and not st.session_state.db_synced:
        try:
            res_w = supabase.table("wrong_questions").select("question_id").eq("user_id", user_id).execute()
            st.session_state.wrong_ids = {item["question_id"] for item in res_w.data}
            res_p = supabase.table("user_progress").select("category, last_index").eq("user_id", user_id).execute()
            st.session_state.all_progress = {item["category"]: item["last_index"] for item in res_p.data}
            st.session_state.index = st.session_state.all_progress.get(category, 0)
            st.session_state.db_synced = True
        except: pass

    mode = st.radio("モード", ["通常学習", "苦手克服 🔥", "忘却曲線復習 🧠"])
    
    # 1日のノルマ可視化（直近7日間）
    if user_id:
        st.divider()
        st.subheader("📊 1週間の学習量")
        try:
            res_stats = supabase.table("daily_stats").select("study_date, count").eq("user_id", user_id).order("study_date").execute()
            if res_stats.data:
                df = pd.DataFrame(res_stats.data)
                df = df.set_index("study_date")
                st.bar_chart(df["count"])
                st.caption(f"今日の解答数: {df.iloc[-1]['count'] if not df.empty else 0} 問")
        except: st.write("グラフの読み込みに失敗しました")

# =========================
# 問題抽出（忘却曲線ロジック）
# =========================
all_target = questions_dict.get(category, [])
if mode == "苦手克服 🔥":
    target = [q for q in all_target if q["id"] in st.session_state.wrong_ids]
elif mode == "忘却曲線復習 🧠":
    # 本来はDBのlast_reviewed_atを使うが、簡易版として「苦手リスト」からランダムに抽出
    target = [q for q in all_target if q["id"] in st.session_state.wrong_ids]
    import random
    random.seed(datetime.now().day) # 日替わりで順序を変える
    random.shuffle(target)
else:
    target = all_target

if not target:
    st.success("🎉 対象の問題はありません！"); st.stop()

if st.session_state.index >= len(target): st.session_state.index = 0
q = target[st.session_state.index]

# =========================
# メイン画面
# =========================
st.title(f"📖 {category}")
col_prog1, col_prog2 = st.columns([4, 1])
with col_prog1:
    prog_val = min((st.session_state.index + 1) / len(target), 1.0)
    st.progress(prog_val)
with col_prog2:
    st.write(f"{int(prog_val*100)}%")

st.markdown(f"### Q. {q['q']}")

col_a, col_b = st.columns(2)
user_ans = None
if not st.session_state.answered:
    if col_a.button("○ 正解", use_container_width=True): user_ans, st.session_state.answered = "○", True
    if col_b.button("× 不正解", use_container_width=True): user_ans, st.session_state.answered = "×", True

if st.session_state.answered:
    if user_ans: st.session_state.last_ans = user_ans
    
    if st.session_state.last_ans == q["a"]:
        st.success("✨ 正解！")
        if q["id"] in st.session_state.wrong_ids:
            st.session_state.wrong_ids.remove(q["id"])
            if user_id: supabase.table("wrong_questions").delete().eq("user_id", user_id).eq("question_id", q["id"]).execute()
    else:
        st.error(f"不正解！ 正解は {q['a']}")
        if q["id"] not in st.session_state.wrong_ids:
            st.session_state.wrong_ids.add(q["id"])
            if user_id: 
                supabase.table("wrong_questions").upsert({"user_id": user_id, "question_id": q["id"], "category": category, "last_reviewed_at": datetime.now().isoformat()}).execute()
    
    st.info(f"💡 **解説**\n\n{q['tips']}")
    
    if st.button("次の問題へ ➡️", use_container_width=True):
        log_study_count(user_id) # 解答数をカウント
        st.session_state.index += 1
        st.session_state.answered = False
        if mode == "通常学習" and user_id:
            supabase.table("user_progress").upsert({"user_id": user_id, "category": category, "last_index": st.session_state.index}).execute()
        st.rerun()