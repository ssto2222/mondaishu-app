import streamlit as st
import json
import random
import os

# --- 設定・データ読み込み ---
st.set_page_config(page_title="社労士試験 過去問完全攻略", layout="centered")

def load_questions():
    if not os.path.exists('questions.json'):
        return {
            "労働基準法_基本問題 (100問)": [
                {"id": 1, "q": "労働者が未成年の場合、親権者が代わって賃金を受け取ることができる。", "a": "×", "tips": "直接払の原則。未成年者本人に支払わなければなりません。"},
                {"id": 2, "q": "有給休暇の時効は2年である。", "a": "○", "tips": "労働基準法における年次有給休暇の時効は2年です。"},
                {"id": 3, "q": "平均賃金の計算において、家族手当は算入しない。", "a": "×", "tips": "家族手当は平均賃金の算定基礎に含まれます。"}
            ],
            "労働安全衛生法_基本問題 (100問)": []
        }
    with open('questions.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# セッション状態の初期化
if 'all_questions' not in st.session_state:
    st.session_state.all_questions = load_questions()
if 'current_index' not in st.session_state:
    st.session_state.current_index = 0
if 'show_answer' not in st.session_state:
    st.session_state.show_answer = False
if 'shuffled_indices' not in st.session_state:
    st.session_state.shuffled_indices = []
if 'user_answer' not in st.session_state:
    st.session_state.user_answer = None
if 'wrong_answers' not in st.session_state:
    st.session_state.wrong_answers = set()

# --- サイドバーの設定 ---
st.sidebar.title("📚 学習設定")

subject_list = sorted(list(set([k.split('_')[0] for k in st.session_state.all_questions.keys()])))
selected_subject = st.sidebar.selectbox("科目を選択", subject_list)

difficulty_list = [k.split('_')[1] for k in st.session_state.all_questions.keys() if k.startswith(selected_subject)]
selected_difficulty = st.sidebar.selectbox("難易度を選択", difficulty_list)

current_key = f"{selected_subject}_{selected_difficulty}"
base_questions = st.session_state.all_questions.get(current_key, [])

# --- 苦手克服モードの切り替え ---
st.sidebar.divider()
st.sidebar.subheader("🎯 学習モード")
mistake_only = st.sidebar.checkbox(f"苦手克服モード ({len(st.session_state.wrong_answers)}問)")

if mistake_only:
    questions = [q for q in base_questions if q['id'] in st.session_state.wrong_answers]
else:
    questions = base_questions

# リセット処理
state_key = current_key + str(mistake_only)
if 'last_key' not in st.session_state or st.session_state.last_key != state_key:
    st.session_state.last_key = state_key
    st.session_state.current_index = 0
    st.session_state.show_answer = False
    st.session_state.shuffled_indices = list(range(len(questions)))
    if not mistake_only:
        random.shuffle(st.session_state.shuffled_indices)

# --- 問題直接選択機能 ---
if questions:
    st.sidebar.divider()
    # 苦手モード時は件数が変わるので動的に最大値を調整
    max_val = max(1, len(questions))
    selected_num = st.sidebar.slider("問題ジャンプ", 1, max_val, min(st.session_state.current_index + 1, max_val))
    if selected_num != st.session_state.current_index + 1:
        st.session_state.current_index = selected_num - 1
        st.session_state.show_answer = False
        st.session_state.user_answer = None

# --- メインコンテンツ ---
st.title(f"✍️ {selected_subject}")
st.subheader(f"{selected_difficulty} {'[苦手克服モード]' if mistake_only else ''}")

if not questions:
    if mistake_only:
        st.success("苦手な問題はすべて克服しました！おめでとうございます！")
    else:
        st.warning("問題が見つかりません。")
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
        if st.button("次の問題へ ➡️", use_container_width=True):
            st.session_state.current_index = (st.session_state.current_index + 1) % len(questions)
            st.session_state.show_answer = False
            st.session_state.user_answer = None
            st.rerun()

    if st.session_state.show_answer:
        st.divider()
        is_correct = (st.session_state.user_answer == q_data['a'])
        
        if is_correct:
            st.success(f"正解！ 答えは [{q_data['a']}] です。")
        else:
            st.error(f"不正解... 答えは [{q_data['a']}] です。")
            st.session_state.wrong_answers.add(q_data['id'])
            
        with st.expander("💡 解説・チップス", expanded=True):
            st.write(q_data['tips'])
            # 手動削除ボタン
            if q_data['id'] in st.session_state.wrong_answers:
                if st.button("✨ この問題を克服したのでリストから消す", type="primary"):
                    st.session_state.wrong_answers.remove(q_data['id'])
                    st.toast(f"ID:{q_data['id']} を苦手リストから削除しました！")
                    st.rerun()

# --- フッター ---
st.sidebar.divider()
if st.sidebar.button("全苦手記録をリセット"):
    st.session_state.wrong_answers = set()
    st.rerun()