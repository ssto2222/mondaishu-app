import streamlit as st
import random
import os
import json

# --- 1. データ定義 (30問) ---
QUIZ_DATA = [
    (1, "総則", "労働条件の原則", "労働基準法で定める基準を理由として、労働条件を低下させることは禁止されているが、その向上を図るように努める義務までは規定されていない。", "×", "第1条。向上を図るように「努めなければならない」と訓示的規定があります。", "S"),
    (2, "総則", "平均賃金", "平均賃金の算定において、算定事由発生日以前3ヶ月間に支払われた賃金総額を、その期間の「総日数」で除して計算する。", "○", "原則は「総日数（暦日数）」です。労働日数ではありません。", "S"),
    (3, "労働契約", "労働条件の明示", "賃金の決定、計算及び支払の方法については、書面の交付（本人の希望があれば電子媒体も可）により明示しなければならない。", "○", "絶対的明示事項かつ書面交付義務がある重要項目です。", "S"),
    (4, "労働契約", "賠償予定", "労働者が遅刻や欠勤をした場合に備え、あらかじめ「1回につき5,000円を徴収する」といった違約金を定める契約をすることができる。", "×", "第16条。違約金を定めたり損害賠償額を予定する契約は禁止されています。", "S"),
    (5, "労働契約", "解雇制限", "産前産後の女性が休業する期間及びその後30日間は、使用者は原則として解雇してはならない。", "○", "第19条。業務上の傷病による休業期間中も同様です。", "S"),
    (6, "労働契約", "解雇予告", "解雇予告手当として平均賃金の30日分以上を支払えば、予告期間を置かずに即時解雇することができる。", "○", "30日分の支払いで即時解雇可能です。", "S"),
    (7, "賃金", "賃金支払", "賃金は、通貨で、直接労働者に、全額を、毎月1回以上、一定の期日を定めて支払わなければならない。", "○", "賃金支払の五原則です。", "S"),
    (8, "賃金", "休業手当", "使用者の責に帰すべき事由による休業の場合、平均賃金の100分の60以上の休業手当を支払わなければならない。", "○", "第26条。天災事変など不可抗力の場合は不要です。", "S"),
    (9, "労働時間", "法定労働時間", "特例対象事業場（常時10人未満の商業・サービス業等）を除き、1週の法定労働時間は40時間である。", "○", "原則は週40時間、1日8時間です。", "S"),
    (10, "労働時間", "休憩", "労働時間が8時間を超える場合、少なくとも1時間の休憩時間を労働時間の途中に与えなければならない。", "○", "6時間超は45分、8時間超は1時間です。", "S"),
    (11, "労働時間", "36協定", "36協定を締結していても、1ヶ月の時間外労働および休日労働の合計は100時間未満でなければならない。", "○", "上限規制の絶対的なルールです。", "S"),
    (12, "労働時間", "深夜業", "午後10時から午前5時までの間に労働させた場合、2割5分以上の割増賃金を支払わなければならない。", "○", "深夜割増の規定です。", "A"),
    (13, "労働時間", "フレックス", "フレックスタイム制の清算期間は、最長で6ヶ月まで設定することができる。", "×", "最長で3ヶ月です。", "A"),
    (14, "労働時間", "みなし労働", "事業場外労働で労働時間の算定が困難なときは、通常は「所定労働時間」労働したものとみなす。", "○", "第38条の2第1項。", "B"),
    (15, "有給休暇", "付与要件", "雇入れから6ヶ月勤務し、全労働日の8割以上出勤した場合、10日の有給休暇を付与しなければならない。", "○", "これが有給の最低付与日数です。", "S"),
    (16, "有給休暇", "時記指定義務", "10日以上の有給が付与される労働者に対し、使用者は毎年5日を時季指定して取得させる義務がある。", "○", "働き方改革による重要項目です。", "S"),
    (17, "有給休暇", "比例付与", "週所定労働時間が30時間未満かつ週所定労働日数が4日の労働者にも、有給休暇は比例付与される。", "○", "パートタイム労働者への比例付与規定です。", "A"),
    (18, "年少者", "最低年齢", "児童が満15歳に達した日以降の最初の3月31日を経過するまで、原則として労働者として使用できない。", "○", "義務教育終了までの児童労働禁止規定です。", "S"),
    (19, "妊産婦", "深夜業制限", "妊産婦が請求した場合、使用者は深夜業をさせてはならない。", "○", "第66条第3項。請求が前提です。", "A"),
    (20, "就業規則", "作成義務", "常時10人以上の労働者を使用する事業場は、就業規則を作成し届出なければならない。", "○", "第89条。人数にはアルバイト等も含みます。", "S"),
    (21, "就業規則", "意見聴取", "就業規則の作成にあたり、過半数組合（なければ代表者）の同意を得なければならない。", "×", "「同意」ではなく「意見を聴く」ことが義務です。", "S"),
    (22, "寄宿舎", "私生活", "使用者は、寄宿舎生活をする労働者の外出を制限してはならない。", "○", "第94条。私生活の自由の保障です。", "B"),
    (23, "災害補償", "療養補償", "労働者が業務上負傷した場合、使用者はその費用で必要な療養を行い、又は必要な療養の費用を負担しなければならない。", "○", "無過失責任の原則です。", "A"),
    (24, "監督官", "権限", "労働基準監督官は、事業場に立ち入り、帳簿書類の提出を求め、関係者に尋問することができる。", "○", "第101条。強力な権限が与えられています。", "S"),
    (25, "総則", "男女同一賃金", "女性であることを理由として、賃金について男性と差別的取扱いをしてはならない。", "○", "第4条。性別を理由とした賃金差別の禁止です。", "S"),
    (26, "労働契約", "前借金相殺", "前借金と賃金の相殺は、労働者の自由な意思に基づく同意があれば禁止されない。", "×", "第17条。同意があっても相殺禁止です（身分的拘束の防止）。", "A"),
    (27, "労働時間", "一斉休憩", "運輸業や商業など特定の業種を除き、休憩時間は原則として一斉に与えなければならない。", "○", "一斉付与の原則です。", "B"),
    (28, "年少者", "証明書", "満18歳に満たない者を使用する場合、その年齢を証明する戸籍証明書を事業場に備え付けなければならない。", "○", "第57条。", "A"),
    (29, "有給休暇", "時季変更権", "使用者の時季変更権は、事業の正常な運営を妨げる場合にのみ行使できる。", "○", "単に「忙しいから」だけでは認められにくい権利です。", "A"),
    (30, "賃金", "非常時払", "労働者が結婚の費用のために未払賃金を請求した場合、支払期日前でも支払わなければならない。", "○", "第25条。結婚は非常時のひとつに含まれます。", "B")
]

SAVE_FILE = "study_save_data.json"

# --- 2. 保存/読込ロジック ---
def load_save_data():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            return json.load(f)
    return {"wrong_ids": [], "solved_ids": [], "last_qid": None}

def save_current_state(wrong_ids, solved_ids, last_qid):
    with open(SAVE_FILE, "w") as f:
        json.dump({"wrong_ids": list(wrong_ids), "solved_ids": list(solved_ids), "last_qid": last_qid}, f)

# --- 3. UI 構築 ---
st.set_page_config(page_title="労基法30：継続学習版", layout="centered")

# スマホ向けボタン
st.markdown("""<style>div.stButton > button { height: 4em; width: 100%; font-size: 24px !important; border-radius: 12px; margin-bottom: 5px; }</style>""", unsafe_allow_html=True)

# セッション管理
if "data" not in st.session_state:
    st.session_state.data = load_save_data()
if "judged" not in st.session_state:
    st.session_state.judged = False
if "finished" not in st.session_state:
    st.session_state.finished = False

st.title("⚖️ 労基法30：反復演習")

# 進行状況の計算
solved_ids = set(st.session_state.data["solved_ids"])
wrong_ids = set(st.session_state.data["wrong_ids"])
remaining_questions = [q for q in QUIZ_DATA if q[0] not in solved_ids]

# サイドバー：ステータス
st.sidebar.header("進捗状況")
st.sidebar.write(f"解答済み: {len(solved_ids)} / 30")
st.sidebar.write(f"残り問題: {len(remaining_questions)} 問")
st.sidebar.write(f"現在の苦手数: {len(wrong_ids)}")

if st.sidebar.button("全データをリセットして最初から"):
    if os.path.exists(SAVE_FILE): os.remove(SAVE_FILE)
    st.session_state.data = {"wrong_ids": [], "solved_ids": [], "last_qid": None}
    st.session_state.judged = False
    st.session_state.finished = False
    st.rerun()

# --- メインロジック ---
if not remaining_questions and not st.session_state.judged:
    st.balloons()
    st.success("全30問完了しました！お疲れ様でした。")
    if st.button("苦手な問題だけを再開する"):
        st.session_state.data["solved_ids"] = [i for i in range(1, 31) if str(i) not in wrong_ids]
        st.rerun()
else:
    # 問題の選定（まだ解いていないものから1つ）
    if "current_q" not in st.session_state or st.session_state.current_q[0] in solved_ids:
        st.session_state.current_q = random.choice(remaining_questions)

    q = st.session_state.current_q
    
    st.progress(len(solved_ids) / 30)
    st.write(f"**第 {len(solved_ids) + 1} 問目** ({q[1]})")
    st.info(f"【論点：{q[2]}】\n\n{q[3]}")

    if not st.session_state.judged:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("◯"):
                st.session_state.user_choice = "○"
                st.session_state.judged = True
                st.rerun()
        with c2:
            if st.button("✕"):
                st.session_state.user_choice = "×"
                st.session_state.judged = True
                st.rerun()
        
        if st.button("中断して保存する", key="save_exit"):
            save_current_state(wrong_ids, solved_ids, q[0])
            st.warning("状態を保存しました。ブラウザを閉じても大丈夫です。")
    
    else:
        # 判定
        is_correct = (st.session_state.user_choice == q[4])
        if is_correct:
            st.success("✅ 正解！")
            if str(q[0]) in wrong_ids: wrong_ids.remove(str(q[0]))
        else:
            st.error(f"❌ 不正解... (正解は {q[4]})")
            wrong_ids.add(str(q[0]))
        
        st.write(f"**解説:** {q[5]}")
        solved_ids.add(q[0])
        
        # 毎回答ごとに自動保存
        save_current_state(wrong_ids, solved_ids, q[0])
        st.session_state.data["solved_ids"] = list(solved_ids)
        st.session_state.data["wrong_ids"] = list(wrong_ids)

        if st.button("次の問題へ"):
            st.session_state.judged = False
            st.rerun()