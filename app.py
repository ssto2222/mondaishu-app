import streamlit as st
import json
import glob
import os
from supabase import create_client

st.set_page_config(page_title="社労士合格アプリ")

# =========================
# Supabase接続
# =========================
# secrets.tomlに設定が必要
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================
# 問題読み込み (JSONファイルを検索)
# =========================
@st.cache_data
def load_all_questions():
    """
    カレントディレクトリ内の .json ファイルを検索し、
    { "ファイル名": [問題データ], ... } の辞書を作成する
    """
    all_data = {}
    # カレントディレクトリ内のjsonファイルを取得
    json_files = glob.glob("*.json")
    
    for file_path in json_files:
        # ファイル名を科目名として使用 (例: "07_国民年金法.json" -> "07_国民年金法")
        subject_name = os.path.splitext(os.path.basename(file_path))[0]
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                questions = json.load(f)
                if isinstance(questions, list):
                    all_data[subject_name] = questions
        except Exception as e:
            st.error(f"ファイルの読み込みに失敗しました: {file_path} ({e})")
            
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
    # 科目ごとに苦手問題を管理する場合は辞書にする
    st.session_state.wrong_ids = set()

if "current_category" not in st.session_state:
    st.session_state.current_category = ""

# =========================
# サイドバー
# =========================
with st.sidebar:
    st.title("設定")
    user_id = st.text_input("ユーザーID")

    # JSONファイルから取得した科目名一覧を選択肢にする
    category_list = sorted(list(questions_dict.keys()))
    category = st.selectbox("科目", category_list)

    # 科目が変更されたらインデックスをリセット
    if category != st.session_state.current_category:
        st.session_state.current_category = category
        st.session_state.index = 0
        st.session_state.answered = False

    mode = st.radio("モード", ["通常", "苦手克服"])

# =========================
# 問題取得処理
# =========================
target = questions_dict.get(category, [])

if mode == "苦手克服":
    # session_state.wrong_ids に含まれるIDの問題のみ抽出
    target = [q for q in target if q["id"] in st.session_state.wrong_ids]

if not target:
    st.info("対象となる問題がありません（苦手克服モードの場合は正解するとリストから消えます）")
    st.stop()

# インデックスが範囲外にならないよう調整
if st.session_state.index >= len(target):
    st.session_state.index = 0

q = target[st.session_state.index]

# =========================
# メイン画面表示
# =========================
st.title(category)
st.subheader(f"問題 {st.session_state.index + 1} / {len(target)}")

st.write(q["q"])

# 回答用ボタン
col1, col2 = st.columns(2)
user_ans = None

with col1:
    if st.button("○", use_container_width=True, disabled=st.session_state.answered):
        user_ans = "○"
        st.session_state.answered = True

with col2:
    if st.button("×", use_container_width=True, disabled=st.session_state.answered):
        user_ans = "×"
        st.session_state.answered = True

# =========================
# 回答判定・解説表示
# =========================
if st.session_state.answered:
    # 直前のクリックで代入されたuser_ansがNoneの場合は、セッション等から判定を保持する必要があるため
    # ここではボタンが押された瞬間の判定ロジックを工夫
    
    # 判定ロジックをボタン押下時に完結させるために一時変数を利用
    if "last_ans" not in st.session_state:
        st.session_state.last_ans = ""
    
    if user_ans:
        st.session_state.last_ans = user_ans

    # 正解・不正解の判定
    if st.session_state.last_ans == q["a"]:
        st.success("正解！")
        if q["id"] in st.session_state.wrong_ids:
            st.session_state.wrong_ids.remove(q["id"])
    else:
        st.error(f"不正解... 正解は {q['a']} です。")
        st.session_state.wrong_ids.add(q["id"])
        
        # Supabaseへの保存
        if user_id:
            try:
                supabase.table("wrong_questions").insert({
                    "user_id": user_id,
                    "question_id": q["id"],
                    "category": category  # どの科目の問題かも保存
                }).execute()
            except Exception as e:
                pass # エラー時はサイレントにスルー

    # 解説表示
    with st.expander("解説を見る", expanded=True):
        st.info(q["tips"])

    # 次へボタン
    if st.button("次の問題へ"):
        st.session_state.index += 1
        st.session_state.answered = False
        st.session_state.last_ans = ""
        st.rerun()

# =========================
# 進捗管理
# =========================
st.divider()
st.write(f"この科目の苦手問題数: {len([q for q in questions_dict[category] if q['id'] in st.session_state.wrong_ids])}")

# プログレスバー
if len(target) > 0:
    progress_val = (st.session_state.index) / len(target)
    st.progress(min(progress_val + (1/len(target) if st.session_state.answered else 0), 1.0))