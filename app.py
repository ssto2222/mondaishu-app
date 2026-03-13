import streamlit as st
import json
import random
import os

# --- 設定・データ読み込み ---
st.set_page_config(page_title="社労士試験 過去問完全攻略", layout="centered")

def load_questions():
    if not os.path.exists('questions.json'):
        # ファイルがない場合のサンプルデータ
        return {
            "労働基準法_基本問題 (100問)": [],
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

# --- サイドバーの設定 ---
st.sidebar.title("📚 学習設定")

# jsonのキーから科目名を抽出 (例: "労働基準法")
subject_list = sorted(list(set([k.split('_')[0] for k in st.session_state.all_questions.keys()])))
selected_subject = st.sidebar.selectbox("科目を選択", subject_list)

# 選択された科目に属する難易度を抽出 (例: "基本問題 (100問)")
difficulty_list = [k.split('_')[1] for k in st.session_state.all_questions.keys() if k.startswith(selected_subject)]
selected_difficulty = st.sidebar.selectbox("難易度を選択", difficulty_list)

# 最終的なキーを決定
current_key = f"{selected_subject}_{selected_difficulty}"
questions = st.session_state.all_questions.get(current_key, [])

# 問題リストが切り替わった時のリセット処理
if 'last_key' not in st.session_state or st.session_state.last_key != current_key:
    st.session_state.last_key = current_key
    st.session_state.current_index = 0
    st.session_state.show_answer = False
    st.session_state.shuffled_indices = list(range(len(questions)))
    random.shuffle(st.session_state.shuffled_indices)

# --- メインコンテンツ ---
st.title(f"✍️ {selected_subject}")
st.subheader(selected_difficulty)

if not questions:
    st.warning("問題が登録されていません。questions.jsonを確認してください。")
else:
    # 現在の問題を取得
    idx = st.session_state.shuffled_indices[st.session_state.current_index]
    q_data = questions[idx]

    # プログレスバー
    progress = (st.session_state.current_index + 1) / len(questions)
    st.progress(progress)
    st.write(f"問題 {st.session_state.current_index + 1} / {len(questions)}")

    # 問題カードの表示
    st.info(f"**【問題 ID: {q_data['id']}】**\n\n{q_data['q']}")

    # 回答操作
    col1, col2 = st.columns(2)
    with col1:
        if st.button("答えを表示", use_container_width=True):
            st.session_state.show_answer = True
    with col2:
        if st.button("次の問題へ", use_container_width=True):
            if st.session_state.current_index < len(questions) - 1:
                st.session_state.current_index += 1
            else:
                st.balloons()
                st.success("全問終了です！お疲れ様でした！")
                st.session_state.current_index = 0
                random.shuffle(st.session_state.shuffled_indices)
            st.session_state.show_answer = False
            st.rerun()

    # 答えの表示
    if st.session_state.show_answer:
        st.divider()
        ans_color = "green" if q_data['a'] == "○" else "red"
        st.markdown(f"### 正解: :{ans_color}[{q_data['a']}]")
        
        with st.expander("💡 解説・チップス", expanded=True):
            st.write(q_data['tips'])

# --- フッター ---
st.sidebar.divider()
if st.sidebar.button("問題をシャッフルしてやり直す"):
    random.shuffle(st.session_state.shuffled_indices)
    st.session_state.current_index = 0
    st.session_state.show_answer = False
    st.rerun()

st.sidebar.caption("Data source: questions.json")