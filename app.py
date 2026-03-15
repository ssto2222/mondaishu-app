import streamlit as st
from st_supabase_connection import SupabaseConnection
import random
from collections import Counter
import openai
import json

st.set_page_config(page_title="社労士合格AI", layout="centered")

# ======================
# Supabase接続
# ======================

conn = st.connection("supabase", type=SupabaseConnection)

# ======================
# OpenAI
# ======================

openai.api_key = st.secrets["OPENAI_API_KEY"]

# ======================
# 問題取得
# ======================

def load_questions(category):

    res = conn.table("questions")\
        .select("*")\
        .eq("category", category)\
        .execute()

    return res.data


# ======================
# AI問題生成
# ======================

def generate_ai_questions(category):

    prompt = f"""
社労士試験の{category}の○×問題を5問作成
json形式

[
 {{
  "question":"",
  "answer":"○",
  "explanation":"",
  "topic":""
 }}
]
"""

    res = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}]
    )

    text = res.choices[0].message.content

    data = json.loads(text)

    for q in data:

        new_id = random.randint(1000000,9999999)

        conn.table("questions").insert({
            "id":new_id,
            "category":category,
            "type":"ox",
            "question":q["question"],
            "answer":q["answer"],
            "explanation":q["explanation"],
            "topic":q["topic"],
            "difficulty":2
        }).execute()


# ======================
# AI解説
# ======================

def ai_explain(text):

    prompt=f"""
次の社労士問題をわかりやすく解説してください

{text}
"""

    res=openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}]
    )

    return res.choices[0].message.content


# ======================
# セッション
# ======================

if "index" not in st.session_state:
    st.session_state.index = 0

if "correct" not in st.session_state:
    st.session_state.correct = 0

if "total" not in st.session_state:
    st.session_state.total = 0

if "topics" not in st.session_state:
    st.session_state.topics = []

# ======================
# サイドバー
# ======================

with st.sidebar:

    st.title("設定")

    user_id = st.text_input("ユーザーID")

    categories = [
        "01_労働基準法",
        "02_労働安全衛生法",
        "03_労災保険法",
        "04_雇用保険法",
        "05_労働保険徴収法",
        "06_健康保険法",
        "07_国民年金法",
        "08_厚生年金保険法",
        "09_労一",
        "10_社一"
    ]

    category = st.selectbox("科目", categories)

    mode = st.radio("モード", ["通常","苦手"])

    if st.button("AI問題生成"):
        generate_ai_questions(category)
        st.success("問題追加")

# ======================
# 問題ロード
# ======================

questions = load_questions(category)

if mode == "苦手":

    wrong = conn.table("wrong_questions")\
        .select("question_id")\
        .eq("user_id", user_id)\
        .execute()

    ids = [w["question_id"] for w in wrong.data]

    questions = [q for q in questions if q["id"] in ids]

if not questions:

    st.info("問題がありません")
    st.stop()

random.shuffle(questions)

q = questions[st.session_state.index]

# ======================
# 問題表示
# ======================

st.title(category)

st.subheader(q["question"])

user_ans=None

if q["type"]=="ox":

    col1,col2 = st.columns(2)

    if col1.button("○"):
        user_ans="○"

    if col2.button("×"):
        user_ans="×"

elif q["type"]=="choice":

    user_ans = st.radio("選択", q["choices"])

# ======================
# 回答
# ======================

if st.button("回答"):

    st.session_state.total += 1

    correct = q["answer"]

    if user_ans == correct:

        st.success("正解")

        st.session_state.correct += 1

    else:

        st.error(f"不正解 正解:{correct}")

        conn.table("wrong_questions").insert({
            "user_id":user_id,
            "question_id":q["id"]
        }).execute()

    st.info(q["explanation"])

    st.session_state.topics.append(q["topic"])

    with st.expander("AI解説"):

        st.write(ai_explain(q["question"]))

    if st.button("次へ"):

        st.session_state.index += 1

        conn.table("study_log").insert({
            "user_id":user_id,
            "question_id":q["id"],
            "result":user_ans
        }).execute()

        st.rerun()

# ======================
# 弱点分析
# ======================

st.divider()

st.subheader("弱点分析")

if st.session_state.topics:

    counter = Counter(st.session_state.topics)

    st.write(counter.most_common(5))

# ======================
# 合格率予測
# ======================

st.divider()

if st.session_state.total > 0:

    rate = st.session_state.correct / st.session_state.total

    st.metric("正答率", f"{rate*100:.1f}%")

    if rate > 0.7:
        st.success("合格圏")

    elif rate > 0.6:
        st.warning("ボーダー")

    else:
        st.error("要強化")

# ======================
# 進捗
# ======================

progress = st.session_state.index / len(questions)

st.progress(progress)