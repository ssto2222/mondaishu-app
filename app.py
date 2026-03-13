import streamlit as st
import json
import random
import os
import shelve  # 状態保存用

# --- 設定・データ読み込み ---
st.set_page_config(page_title="社労士試験 過去問完全攻略", layout="centered")

def load_questions():
    if not os.path.exists('questions.json'):
        return {
            "労働基準法_基本問題 (100問)": [
                {"id": 1, "q": "労働者が未成年の場合、親権者が代わって賃金を受け取ることができる。", "a": "×", "tips": "直接払の原則。"},
                {"id": 2, "q": "有給休暇の時効は2年である。", "a": "○", "tips": "時効は2年です。"},
                {"id": 3, "q": "平均賃金の計算において、家族手当は算入しない。", "a": "×", "tips": "家族手当は含まれます。"}
            ],
            "労働安全衛生法_基本問題 (100問)": []
        }
    with open('questions.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# --- 永続化ストレージの管理 ---
def save_app_state():
    with shelve.open('app_state_db') as db:
        db['wrong_answers'] = st.session_state.wrong_answers
        db['last_key'] = st.session_state.get('last_key')
        db['current_index'] = st.session_state.current_index
        db['shuffled_indices'] = st.session_state.shuffled_indices

def load_app_state():
    if os.path.exists('app_state_db.db') or os.path.exists('app_state_db.dat'):
        with shelve.open('app_state_db') as db:
            st.session_state.wrong_answers = db.get('wrong_answers', set())
            st.session_state.last_key = db.get('last_key', None)
            st.session_state.current_index = db.get('current_index', 0)
            st.session_state.shuffled_indices = db.get('shuffled_indices', [])
            return True
    return False

# セッション状態の初期化
if 'all_questions' not in st.session_state:
    st.session_state.all_questions = load_questions()
    if not load_app_state():
        st.session_state.wrong_answers = set()
        st.session_state.current_index = 0
        st.session_state.shuffled_indices = []

if 'show_answer' not in st.session_state:
    st.session_state.show_answer = False
if 'user_answer' not in st.session_state:
    st.session_state.user_answer = None

# --- サイドバーの設定 ---
st.sidebar.title("📚 学習設定")

subject_list = sorted(list(set([k.split('_')[0] for k in st.session_state.all_questions.keys()])))
selected_subject = st.sidebar.selectbox("科目を選択", subject_list)

difficulty_list = [k.split('_')[1] for k in st.session_state.all_questions.keys() if k.startswith(selected_subject)]
selected_difficulty = st.sidebar.selectbox("難易度を選択", difficulty_list)

current_key = f"{selected_subject}_{selected_difficulty}"
base_questions = st.session_state.all_questions.get(current_key, [])

st.sidebar.divider()
st.sidebar.subheader("🎯 学習モード")
mistake_only = st.sidebar.checkbox(f"苦手克服モード ({len(st.session_state.wrong_answers)}問)")

# 出題リストの生成
if mistake_only:
    questions = [q for q in base_questions if q['id'] in st.session_state.wrong_answers]
else:
    questions = base_questions

# 状態が変わった場合のリセット（保存されたキーと違う場合のみ）
state_key = current_key + str(mistake_only)
if st.session_state.get('last_key') != state_key:
    st.session_state.last_key = state_key
    st.session_state.current_index = 0
    st.session_state.shuffled_indices = list(range(len(questions)))
    if not mistake_only:
        random.shuffle(st.session_state.shuffled_indices)
    save_app_state()

# --- 問題選択/ジャンプ ---
if questions:
    st.sidebar.divider()
    max_q = len(questions)
    # インデックスが範囲外にならないよう調整
    safe_index = min(st.session_state.current_index + 1, max_q)
    selected_num = st.sidebar.number_input("問題番号へ移動", 1, max_q, int(safe_index))
    if selected_num != st.session_state.current_index + 1:
        st.session_state.current_index = selected_num - 1
        st.session_state.show_answer = False
        save_app_state()

# --- メインコンテンツ ---
st.title(f"✍️ {selected_subject}")
st.subheader(f"{selected_difficulty} {'[再開中]' if st.session_state.current_index > 0 else ''}")

if not questions:
    st.success("対象の問題はありません。")
else:
    if st.session_state.current_index >= len(questions):
        st.session_state.current_index = 0

    idx = st.session_state.shuffled_indices[st.session_state.current_index]
    q_data = questions[idx]

    st.progress((st.session_state.current_index + 1) / len(questions))
    st.write(f"問題 {st.session_state.current_index + 1} / {len(questions)}")

    st.info(f"**【問題 ID: {q_data['id']}】**\n\n{q_data['q']}")

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("⭕️", use_container_width=True):
            st.session_state.user_answer = "○"
            st.session_state.show_answer = True
    with col2:
        if st.button("❌", use_container_width=True):
            st.session_state.user_answer = "×"
            st.session_state.show_answer = True
    with col3:
        if st.button("次へ (保存して進む) ➡️", use_container_width=True):
            st.session_state.current_index = (st.session_state.current_index + 1) % len(questions)
            st.session_state.show_answer = False
            st.session_state.user_answer = None
            save_app_state() # 進むたびに状態を保存
            st.rerun()

    if st.session_state.show_answer:
        st.divider()
        if st.session_state.user_answer == q_data['a']:
            st.success(f"正解！ [{q_data['a']}]")
        else:
            st.error(f"不正解... [{q_data['a']}]")
            st.session_state.wrong_answers.add(q_data['id'])
            save_app_state()
            
        with st.expander("💡 解説", expanded=True):
            st.write(q_data['tips'])
            if q_data['id'] in st.session_state.wrong_answers:
                if st.button("✨ 克服！リストから消す"):
                    st.session_state.wrong_answers.remove(q_data['id'])
                    save_app_state()
                    st.rerun()

# --- 中断・リセット機能 ---
st.sidebar.divider()
if st.sidebar.button("最初から（シャッフルし直し）"):
    st.session_state.current_index = 0
    random.shuffle(st.session_state.shuffled_indices)
    save_app_state()
    st.rerun()

if st.sidebar.button("全ての学習記録を消去"):
    if os.path.exists('app_state_db.db'): os.remove('app_state_db.db')
    if os.path.exists('app_state_db.dat'): os.remove('app_state_db.dat')
    if os.path.exists('app_state_db.bak'): os.remove('app_state_db.bak')
    if os.path.exists('app_state_db.dir'): os.remove('app_state_db.dir')
    st.session_state.wrong_answers = set()
    st.session_state.current_index = 0
    st.rerun()

st.sidebar.caption("※進捗は自動で保存されています。")