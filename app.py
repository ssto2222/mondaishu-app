import streamlit as st
import json
import glob
import os
from supabase import create_client

st.set_page_config(page_title="社労士合格アプリ", layout="centered")

# =========================
# Supabase接続
# =========================
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("Supabaseの接続設定が見つかりません。Secretsを確認してください。")
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
        except Exception as e:
            st.error(f"読み込み失敗: {file_path} ({e})")
    return all_data

questions_dict = load_all_questions()

# =========================
# セッション状態の初期化
# =========================
if "index" not in st.session_state:
    st.session_state.index = 0
if "answered" not in st.session_state:
    st.session_state.answered = False
if "wrong_ids" not in st.session_state:
    st.session_state.wrong_ids = set()
if "current_category" not in st.session_state:
    st.session_state.current_category = ""
if "last_ans" not in st.session_state:
    st.session_state.last_ans = ""
if "db_synced" not in st.session_state:
    st.session_state.db_synced = False

# =========================
# DB同期関数 (苦手リスト + 進捗再開)
# =========================
def sync_with_supabase(user_id, category):
    """DBからデータを取得。データがなくてもエラーにせず正常終了させる"""
    if user_id and not st.session_state.db_synced:
        try:
            # 1. 苦手問題の同期
            res_wrong = supabase.table("wrong_questions").select("question_id").eq("user_id", user_id).execute()
            # データが空でも res_wrong.data は [] を返すので安全
            st.session_state.wrong_ids = {item["question_id"] for item in res_wrong.data}
            
            # 2. 進捗（インデックス）の同期
            res_prog = supabase.table("user_progress").select("last_index").eq("user_id", user_id).eq("category", category).execute()
            
            # 初回接続時（データがない時）は 0 のままにする
            if res_prog.data and len(res_prog.data) > 0:
                st.session_state.index = res_prog.data[0]["last_index"]
            else:
                st.session_state.index = 0
            
            st.session_state.db_synced = True
        except Exception as e:
            # エラーの詳細を表示（本番では st.log などに流すのが理想）
            st.error(f"同期エラー詳細: {e}") 
            st.warning("初回設定またはネットワークエラーです。このまま学習を始められます。")

def save_progress_to_db(user_id, category, index):
    """現在の進捗をDBに保存する"""
    if user_id:
        try:
            supabase.table("user_progress").upsert({
                "user_id": user_id,
                "category": category,
                "last_index": index
            }).execute()
        except:
            pass

# =========================
# サイドバー
# =========================
with st.sidebar:
    st.title("📊 学習設定")
    user_id = st.text_input("ユーザーID (保存に必要)", placeholder="例: yamada_01")
    
    category_list = sorted(list(questions_dict.keys()))
    if not category_list:
        st.error("JSONファイルが見つかりません。")
        st.stop()
        
    category = st.selectbox("科目を選択", category_list)

    # 科目が変わったら同期フラグをリセット
    if category != st.session_state.current_category:
        st.session_state.current_category = category
        st.session_state.db_synced = False # 新しい科目で同期し直す
        st.session_state.index = 0
        st.session_state.answered = False
        if user_id:
            sync_with_supabase(user_id, category)
        st.rerun()

    if user_id and not st.session_state.db_synced:
        sync_with_supabase(user_id, category)

    mode = st.radio("モード切替", ["通常学習", "苦手克服 🔥"])
    
    if user_id:
        st.success(f"同期中: {user_id}")

# =========================
# 問題抽出
# =========================
all_target = questions_dict.get(category, [])
if mode == "苦手克服 🔥":
    target = [q for q in all_target if q["id"] in st.session_state.wrong_ids]
else:
    target = all_target

if not target:
    if mode == "苦手克服 🔥":
        st.balloons()
        st.success("🎉 この科目の苦手問題はすべてクリアしました！")
    else:
        st.info("対象の問題がありません。")
    st.stop()

# インデックスが範囲外にならないよう調整（苦手克服で問題が減った時用）
if st.session_state.index >= len(target):
    st.session_state.index = 0

q = target[st.session_state.index]

# =========================
# メイン画面表示
# =========================
st.title(f"📖 {category}")
st.caption(f"ID: {q['id']} | {mode}")
st.progress(min((st.session_state.index + 1) / len(target), 1.0))
st.write(f"**Q{st.session_state.index + 1} / {len(target)}**")
st.markdown(f"### {q['q']}")

col1, col2 = st.columns(2)
user_ans = None

with col1:
    if st.button("○ 正解", use_container_width=True, disabled=st.session_state.answered, key="btn_o"):
        user_ans = "○"
        st.session_state.answered = True
with col2:
    if st.button("× 不正解", use_container_width=True, disabled=st.session_state.answered, key="btn_x"):
        user_ans = "×"
        st.session_state.answered = True

# =========================
# 判定ロジック
# =========================
if st.session_state.answered:
    if user_ans:
        st.session_state.last_ans = user_ans

    if st.session_state.last_ans == q["a"]:
        st.success("✨ 正解です！")
        if q["id"] in st.session_state.wrong_ids:
            st.session_state.wrong_ids.remove(q["id"])
            if user_id:
                supabase.table("wrong_questions").delete().eq("user_id", user_id).eq("question_id", q["id"]).execute()
    else:
        st.error(f"残念！ 正解は 【 {q['a']} 】 です。")
        if q["id"] not in st.session_state.wrong_ids:
            st.session_state.wrong_ids.add(q["id"])
            if user_id:
                supabase.table("wrong_questions").upsert({
                    "user_id": user_id,
                    "question_id": q["id"],
                    "category": category
                }).execute()

    st.info(f"💡 **解説**\n\n{q['tips']}")

    if st.button("次の問題へ ➡️", use_container_width=True):
        st.session_state.index += 1
        st.session_state.answered = False
        st.session_state.last_ans = ""
        # 進捗をDBに保存
        if mode == "通常学習": # 苦手モードは件数が変動するため通常時のみ記録
            save_progress_to_db(user_id, category, st.session_state.index)
        st.rerun()

# =========================
# ステータス表示
# =========================
st.divider()
total_subject_questions = len(all_target)
current_wrong_count = len([qid for qid in st.session_state.wrong_ids if any(item['id'] == qid for item in all_target)])
st.write(f"この科目の苦手問題: `{current_wrong_count} / {total_subject_questions}`")