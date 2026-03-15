import streamlit as st
import json
import glob
import os
from supabase import create_client

st.set_page_config(page_title="社労士合格アプリ", layout="centered")

# =========================
# Supabase接続
# =========================
# secrets.toml または Streamlit Cloud の Secrets 設定が必要
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    st.error("Supabaseの接続設定が見つかりません。Secretsを確認してください。")
    st.stop()

# =========================
# 問題読み込み (JSONファイルを検索)
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
    st.session_state.wrong_ids = set() # IDのみを保持
if "current_category" not in st.session_state:
    st.session_state.current_category = ""
if "last_ans" not in st.session_state:
    st.session_state.last_ans = ""
if "db_synced" not in st.session_state:
    st.session_state.db_synced = False

# =========================
# DB同期関数 (永続化のキモ)
# =========================
def sync_with_supabase(user_id):
    """DBからユーザーの苦手問題IDを取得してセッションに復元する"""
    if user_id and not st.session_state.db_synced:
        try:
            response = supabase.table("wrong_questions").select("question_id").eq("user_id", user_id).execute()
            ids = {item["question_id"] for item in response.data}
            st.session_state.wrong_ids = ids
            st.session_state.db_synced = True
        except Exception as e:
            st.warning(f"データ同期に失敗しました。オフラインで続行します。")

# =========================
# サイドバー
# =========================
with st.sidebar:
    st.title("📊 学習設定")
    user_id = st.text_input("ユーザーID (保存に必要)", placeholder="例: yamada_01")
    
    if user_id:
        sync_with_supabase(user_id)
        st.success(f"同期完了: 苦手問題 {len(st.session_state.wrong_ids)}件")

    category_list = sorted(list(questions_dict.keys()))
    if not category_list:
        st.error("JSONファイルが見つかりません。")
        st.stop()
        
    category = st.selectbox("科目を選択", category_list)

    if category != st.session_state.current_category:
        st.session_state.current_category = category
        st.session_state.index = 0
        st.session_state.answered = False
        st.rerun()

    mode = st.radio("モード切替", ["通常学習", "苦手克服 🔥"])

# =========================
# 問題抽出
# =========================
all_target = questions_dict.get(category, [])
if mode == "苦手克服 🔥":
    target = [q for q in all_target if q["id"] in st.session_state.wrong_ids]
else:
    target = all_target

if not target:
    st.info("対象の問題がありません。まずは通常モードで学習しましょう！")
    st.stop()

if st.session_state.index >= len(target):
    st.session_state.index = 0

q = target[st.session_state.index]

# =========================
# メイン画面表示
# =========================
st.title(f"📖 {category}")
st.caption(f"ID: {q['id']} | {mode}")
st.progress(min((st.session_state.index + 1) / len(target), 1.0))
st.write(f"**Q{st.session_state.index + 1}.**")
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
        # 苦手リストから削除
        if q["id"] in st.session_state.wrong_ids:
            st.session_state.wrong_ids.remove(q["id"])
            if user_id:
                # DBからも削除（永続化）
                supabase.table("wrong_questions").delete().eq("user_id", user_id).eq("question_id", q["id"]).execute()
    else:
        st.error(f"残念！ 正解は 【 {q['a']} 】 です。")
        # 苦手リストに追加
        if q["id"] not in st.session_state.wrong_ids:
            st.session_state.wrong_ids.add(q["id"])
            if user_id:
                # DBへ保存（永続化：重複無視はDB側またはロジックで制御）
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
        st.rerun()

# =========================
# ステータス表示
# =========================
st.divider()
total_subject_questions = len(all_target)
current_wrong_count = len([qid for qid in st.session_state.wrong_ids if any(item['id'] == qid for item in all_target)])
st.write(f"この科目の苦手問題: `{current_wrong_count} / {total_subject_questions}`")