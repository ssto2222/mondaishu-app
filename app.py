import streamlit as st
import json
import glob
import os
import pandas as pd
from datetime import datetime
from supabase import create_client

# ページ設定
st.set_page_config(page_title="社労士合格アプリ Pro", layout="wide")

# =========================
# Supabase接続
# =========================
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("Supabase設定が見つかりません。Secretsを確認してください。")
    st.stop()

# =========================
# 問題読み込み (JSONファイルをスキャン)
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
        except: pass
    return all_data

questions_dict = load_all_questions()

# =========================
# セッション状態の初期化
# =========================
if "index" not in st.session_state: st.session_state.index = 0
if "answered" not in st.session_state: st.session_state.answered = False
if "wrong_ids" not in st.session_state: st.session_state.wrong_ids = set()
if "current_category" not in st.session_state: st.session_state.current_category = ""
if "last_ans" not in st.session_state: st.session_state.last_ans = ""
if "all_progress" not in st.session_state: st.session_state.all_progress = {}
if "db_synced" not in st.session_state: st.session_state.db_synced = False

# =========================
# DB操作関数
# =========================
def log_study_count(user_id):
    """解答数を記録（グラフ用）"""
    if user_id:
        try:
            today = datetime.now().date().isoformat()
            res = supabase.table("daily_stats").select("count").eq("user_id", user_id).eq("study_date", today).execute()
            new_count = (res.data[0]["count"] + 1) if res.data else 1
            supabase.table("daily_stats").upsert({"user_id": user_id, "study_date": today, "count": new_count}).execute()
        except: pass

def sync_user_data(user_id, category):
    """指定されたユーザーと科目のデータを同期"""
    try:
        # 1. 苦手問題IDの取得
        res_w = supabase.table("wrong_questions").select("question_id").eq("user_id", user_id).execute()
        st.session_state.wrong_ids = {item["question_id"] for item in res_w.data}
        
        # 2. 全科目の進捗取得
        res_p = supabase.table("user_progress").select("category, last_index").eq("user_id", user_id).execute()
        prog_map = {item["category"]: item["last_index"] for item in res_p.data}
        st.session_state.all_progress = prog_map
        
        # 3. 現在選択中の科目の進捗をセット
        st.session_state.index = prog_map.get(category, 0)
        st.session_state.db_synced = True
    except:
        st.warning("同期に失敗しました。オフラインモードで動作します。")

# =========================
# サイドバー（UI & 統計）
# =========================
with st.sidebar:
    st.title("📊 学習管理")
    user_id = st.text_input("ユーザーID", placeholder="yamada_01")
    
    category_list = sorted(list(questions_dict.keys()))
    if not category_list:
        st.error("JSON問題ファイルが見つかりません。")
        st.stop()
    
    category = st.selectbox("科目を選択", category_list)

    # 科目切り替え時のトリガー
    if category != st.session_state.current_category:
        st.session_state.current_category = category
        st.session_state.db_synced = False # 再同期を走らせる
        st.session_state.answered = False
        if user_id:
            sync_user_data(user_id, category)
        st.rerun()

    # ID入力済みで未同期なら同期
    if user_id and not st.session_state.db_synced:
        sync_user_data(user_id, category)

    mode = st.radio("学習モード", ["通常学習", "苦手克服 🔥", "忘却曲線復習 🧠"])

    # 1週間の学習ノルマグラフ
    if user_id:
        st.divider()
        st.subheader("📈 週間学習グラフ")
        try:
            res_stats = supabase.table("daily_stats").select("study_date, count").eq("user_id", user_id).order("study_date").execute()
            if res_stats.data:
                df = pd.DataFrame(res_stats.data).set_index("study_date")
                st.bar_chart(df["count"])
        except: pass

    # 総合進捗表示
    st.divider()
    st.subheader("🏆 全体進捗")
    total_q = sum(len(v) for v in questions_dict.values())
    done_q = sum(st.session_state.all_progress.get(c, 0) for c in questions_dict.keys())
    # 現在の科目の進捗をリアルタイム反映
    done_q = done_q - st.session_state.all_progress.get(category, 0) + st.session_state.index
    
    rate = (done_q / total_q) if total_q > 0 else 0
    st.metric("トータル達成率", f"{int(rate*100)}%", f"{done_q}/{total_q} 問")
    st.progress(rate)

# =========================
# 問題抽出ロジック
# =========================
all_target = questions_dict.get(category, [])
if mode == "苦手克服 🔥":
    target = [q for q in all_target if q["id"] in st.session_state.wrong_ids]
elif mode == "忘却曲線復習 🧠":
    target = [q for q in all_target if q["id"] in st.session_state.wrong_ids]
    import random
    random.seed(datetime.now().day) # 毎日違う順序
    random.shuffle(target)
else:
    target = all_target

if not target:
    st.success("🎉 このモードの対象問題はすべて完了です！")
    st.stop()

# インデックス調整
if st.session_state.index >= len(target):
    st.session_state.index = 0

q = target[st.session_state.index]

# =========================
# メイン画面表示
# =========================
st.title(f"📖 {category}")
st.caption(f"ID: {q['id']} | {mode}")

cur_prog = min((st.session_state.index + 1) / len(target), 1.0)
st.progress(cur_prog)
st.write(f"**Q{st.session_state.index + 1}** / {len(target)} ({int(cur_prog*100)}%)")

st.markdown(f"### {q['q']}")

col1, col2 = st.columns(2)
user_ans = None

if not st.session_state.answered:
    with col1:
        if st.button("○ 正解", use_container_width=True):
            user_ans, st.session_state.answered = "○", True
    with col2:
        if st.button("× 不正解", use_container_width=True):
            user_ans, st.session_state.answered = "×", True

# 判定
if st.session_state.answered:
    if user_ans: st.session_state.last_ans = user_ans
    
    if st.session_state.last_ans == q["a"]:
        st.success("✨ 正解です！")
        if q["id"] in st.session_state.wrong_ids:
            st.session_state.wrong_ids.remove(q["id"])
            if user_id:
                supabase.table("wrong_questions").delete().eq("user_id", user_id).eq("question_id", q["id"]).execute()
    else:
        st.error(f"残念！ 正解は 【 {q['a']} 】")
        if q["id"] not in st.session_state.wrong_ids:
            st.session_state.wrong_ids.add(q["id"])
            if user_id:
                supabase.table("wrong_questions").upsert({
                    "user_id": user_id, "question_id": q["id"], "category": category
                }).execute()

    st.info(f"💡 **解説**\n\n{q['tips']}")

    if st.button("次の問題へ ➡️", use_container_width=True):
        if user_id:
            log_study_count(user_id) # グラフ用カウント
            if mode == "通常学習":
                # 科目ごとの進捗をDBに保存
                supabase.table("user_progress").upsert({
                    "user_id": user_id, "category": category, "last_index": st.session_state.index + 1
                }).execute()
        
        st.session_state.index += 1
        st.session_state.answered = False
        st.session_state.last_ans = ""
        st.rerun()