from openai import OpenAI

import streamlit as st
from supabase import create_client
import openai
import random
from collections import Counter
import json


client = OpenAI(
    api_key=st.secrets["OPENAI_API_KEY"]
)

st.set_page_config(page_title="社労士AI学習")

# =============================
# Secretsから設定取得
# =============================

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

openai.api_key = st.secrets["OPENAI_API_KEY"]

# =============================
# DBから問題取得
# =============================

def load_questions(category):

    try:

        res = supabase.table("questions") \
            .select("*") \
            .eq("category", category) \
            .execute()

        return res.data

    except Exception as e:

        st.error("Supabaseエラー")
        st.code(str(e))

        return []


# =============================
# AI問題生成
# =============================

def generate_ai_questions(category):

    prompt=f"""
社労士試験の{category}の○×問題を5問作成
JSON形式
[
 {{
  "question":"",
  "answer":"○",
  "explanation":"",
  "topic":""
 }}
]
"""

    try:

        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role":"user","content":prompt}
            ]
        )

    except Exception as e:

        st.error("AI生成エラー")
        st.write("OpenAI制限またはAPIキー問題の可能性")
        st.code(str(e))

        return

    data=json.loads(res.choices[0].message.content)

    for q in data:

        supabase.table("questions").insert({

            "id":random.randint(1000000,9999999),
            "category":category,
            "type":"ox",
            "question":q["question"],
            "answer":q["answer"],
            "explanation":q["explanation"],
            "topic":q["topic"],
            "difficulty":2

        }).execute()

    st.success("問題を追加しました")
# =============================
# AI解説
# =============================

def ai_explain(text):

    prompt=f"""
次の社労士問題を分かりやすく解説

{text}
"""

    res=openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content":prompt}]
    )

    return res.choices[0].message.content


# =============================
# セッション
# =============================

if "index" not in st.session_state:
    st.session_state.index=0

if "correct" not in st.session_state:
    st.session_state.correct=0

if "total" not in st.session_state:
    st.session_state.total=0

if "topics" not in st.session_state:
    st.session_state.topics=[]


# =============================
# サイドバー
# =============================

with st.sidebar:

    user_id=st.text_input("ユーザーID")

    categories=[
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

    category=st.selectbox("科目",categories)

    mode=st.radio("モード",["通常","苦手"])

    if st.button("AI問題生成"):

        generate_ai_questions(category)

        st.success("問題追加")


# =============================
# 問題ロード
# =============================

questions=load_questions(category)

if mode=="苦手":

    wrong=supabase.table("wrong_questions")\
        .select("question_id")\
        .eq("user_id",user_id)\
        .execute()

    ids=[w["question_id"] for w in wrong.data]

    questions=[q for q in questions if q["id"] in ids]


if not questions:

    st.info("問題がありません")

    st.stop()


random.shuffle(questions)

q=questions[st.session_state.index]

# =============================
# 問題表示
# =============================

st.title(category)

st.subheader(q["question"])

user_ans=None

col1,col2=st.columns(2)

if col1.button("○"):
    user_ans="○"

if col2.button("×"):
    user_ans="×"


# =============================
# 回答
# =============================

if st.button("回答"):

    st.session_state.total+=1

    if user_ans==q["answer"]:

        st.success("正解")

        st.session_state.correct+=1

    else:

        st.error(f"不正解 正解:{q['answer']}")

        supabase.table("wrong_questions").insert({
        "user_id":user_id,
        "question_id":q["id"]
        }).execute()


    st.info(q["explanation"])

    st.session_state.topics.append(q["topic"])

    with st.expander("AI解説"):

        st.write(ai_explain(q["question"]))


    if st.button("次へ"):

        st.session_state.index+=1

        supabase.table("study_log").insert({

        "user_id":user_id,
        "question_id":q["id"],
        "result":user_ans

        }).execute()

        st.rerun()


# =============================
# 弱点分析
# =============================

st.divider()

st.subheader("弱点")

if st.session_state.topics:

    counter=Counter(st.session_state.topics)

    st.write(counter.most_common(5))


# =============================
# 合格率予測
# =============================

if st.session_state.total>0:

    rate=st.session_state.correct/st.session_state.total

    st.metric("正答率",f"{rate*100:.1f}%")

    if rate>0.7:
        st.success("合格圏")

    elif rate>0.6:
        st.warning("ボーダー")

    else:
        st.error("要強化")