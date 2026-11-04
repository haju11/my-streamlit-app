
import os
from html import escape
from datetime import datetime, time, timedelta, timezone

import streamlit as st
from openai import OpenAI, OpenAIError

st.set_page_config(page_title="ThumbsUp AI", page_icon="👍🏻", layout="wide")

st.markdown("""
<style>
.stApp {
    background: linear-gradient(180deg, #f1f0ef 0%, #faf9f8 48%, #fff 85%);
    color: #252525;
}
[data-testid="stMainBlockContainer"] { max-width: 58rem; padding-top: 3rem; }
.thumbs-brand {
    display: flex; flex-wrap: wrap; align-items: baseline; gap: .8rem;
    border-bottom: 1px solid #e1dfdf; padding: .5rem 0 1rem; color: #262626;
}
.thumbs-brand strong { font-size: 1.15rem; letter-spacing: -.02em; }
.thumbs-brand span { color: #646262; font-size: .85rem; }
.thumbs-hero { text-align: center; padding: 1rem 0 0; }
.thumbs-label { color: #615e62; font-size: .86rem; letter-spacing: .04em; }
.thumbs-question {
    box-sizing: border-box; max-width: 38rem; min-height: 14rem;
    margin: .9rem auto 1.3rem; padding: clamp(1.2rem, 5vw, 3.5rem);
    display: grid; place-items: center; background: #fff; color: #252525;
    box-shadow: 0 10px 26px #25252512; font-weight: 550;
    font-size: clamp(1.25rem, 3vw, 1.9rem); line-height: 1.55;
    white-space: pre-wrap; overflow-wrap: anywhere;
}
.thumbs-wave { display: block; width: 100%; height: auto; margin: .25rem auto 0; }
.thumbs-hint { margin: .15rem 0 .8rem; color: #595773; }
[data-testid="stMain"] [data-testid="stForm"],
[data-testid="stMain"] [data-testid="stExpander"] details {
    border: 1px solid #e4e0f4; border-radius: 1rem; background: #ffffffc9;
}
[data-testid="stMain"] [data-testid="stExpander"] summary {
    background: #f2f1f1; color: #252525;
}
</style>
<div class="thumbs-brand"><strong>ThumbsUp AI</strong><span>김대리의 음성 출근 준비 비서</span></div>
""", unsafe_allow_html=True)

KST = timezone(timedelta(hours=9))
DEPARTURE_ALERTS = (
    (15, "사원증, 노트북, 회의 자료를 확인하세요."),
    (10, "출발 준비를 마무리하세요."),
    (5, "곧 출발할 시간이에요."),
    (0, "김대리님, 지금 출발할 시간이에요."),
)


@st.fragment(run_every="1s")
def show_departure_reminders():
    plan = st.session_state.get("departure_result")
    if not plan:
        return

    departure, label, details = plan
    now = datetime.now(KST)
    remaining = max(0, int((departure - now).total_seconds() + 0.999))
    minutes, seconds = divmod(remaining, 60)

    with st.container(border=True):
        st.subheader("오늘의 출근" if departure.date() == now.date() else "출근 계획")
        st.markdown(label)
        st.caption(details)
        if now < departure:
            st.metric("출발까지", f"{minutes:02d}:{seconds:02d}")
        else:
            st.write("출발 시각이 되었어요.")

        started = st.session_state.get("departure_alerts_started")
        if started is None:
            if now < departure and st.button("알림 시작"):
                st.session_state.departure_alerts_started = datetime.now(KST)
                st.rerun(scope="app")
        elif st.button("알림 끄기"):
            st.session_state.pop("departure_alerts_started", None)
            st.session_state.pop("departure_last_alert", None)
            st.rerun(scope="app")

        lines = []
        latest_due = None
        for offset, message in DEPARTURE_ALERTS:
            scheduled = departure - timedelta(minutes=offset)
            name = f"{offset}분 전" if offset else "출발 시각"
            if started is not None and started <= scheduled <= now:
                latest_due = (scheduled, message)
            if started is not None and scheduled < started:
                status = " · 건너뜀"
            elif scheduled <= now:
                status = " · 지남"
            else:
                status = ""
            lines.append(f"{scheduled:%m/%d %H:%M} {name}{status}")
        st.caption("  |  ".join(lines))

        if latest_due and st.session_state.get("departure_last_alert") != latest_due[0]:
            st.session_state.departure_last_alert = latest_due[0]
            if (now - latest_due[0]).total_seconds() < 60:
                st.toast(latest_due[1], icon="🔔")
        if latest_due and (now - latest_due[0]).total_seconds() < 60:
            st.warning(latest_due[1])
        st.caption("알림은 앱을 열어둔 동안 화면에 표시됩니다.")


with st.sidebar:
    st.subheader("출퇴근 프로필")
    st.caption("평소 소요시간과 여유 시간을 입력하세요. 현재 세션에서 사용합니다.")
    with st.form("commute_profile_form"):
        subway_minutes = st.number_input("대중교통 소요시간 (분)", 1, 720, 35)
        car_minutes = st.number_input("자가용 소요시간 (분)", 1, 720, 30)
        buffer_minutes = st.number_input("기본 여유 시간 (분)", 0, 180, 10)
        if st.form_submit_button("프로필 저장"):
            st.session_state.departure_defaults = {
                "대중교통": subway_minutes,
                "자가용": car_minutes,
                "buffer": buffer_minutes,
            }
            st.session_state.pop("departure_result", None)
            st.session_state.pop("departure_alerts_started", None)
            st.session_state.pop("departure_last_alert", None)
            st.success("출퇴근 프로필을 저장했어요.")

messages = st.session_state.setdefault("messages", [])
if st.session_state.pop("show_latest_answer", False):
    st.session_state.voice_view = "Listen"
view = st.radio(
    "화면 선택",
    ["Speak", "Listen"],
    key="voice_view",
    horizontal=True,
    label_visibility="collapsed",
)

submitted = False
if view == "Speak":
    latest_question = messages[-2]["content"] if messages else "김대리님, 무엇을 도와드릴까요?"
    hero_label = "최근 질문" if messages else "음성 비서 준비 완료"
    st.markdown(f"""
    <div class="thumbs-hero">
        <span class="thumbs-label">{hero_label}</span>
        <div class="thumbs-question">{escape(latest_question)}</div>
        <svg class="thumbs-wave" viewBox="0 0 800 118" aria-hidden="true">
            <defs>
                <linearGradient id="thumbs-gradient">
                    <stop offset="0" stop-color="#9bb6ff" stop-opacity="0"/>
                    <stop offset=".42" stop-color="#9291ff"/>
                    <stop offset=".58" stop-color="#cb7ff2"/>
                    <stop offset="1" stop-color="#f398d4" stop-opacity="0"/>
                </linearGradient>
            </defs>
            <path fill="url(#thumbs-gradient)" opacity=".47"
                  d="M0 59 C190 59 215 29 285 55 S360 73 400 59
                     S490 25 550 49 S670 59 800 59 C640 59 600 88 530 64
                     S447 46 400 59 S310 90 248 69 S120 59 0 59Z"/>
            <path fill="none" stroke="url(#thumbs-gradient)" stroke-width="2"
                  d="M0 59 Q160 59 210 54 T310 59 T400 59 T495 54 T600 59 T800 59"/>
            <circle cx="400" cy="59" r="44" fill="#a396fb" opacity=".18"/>
            <circle cx="400" cy="59" r="36" fill="#fff" stroke="#d5caff"/>
            <rect x="394" y="44" width="12" height="21" rx="6" fill="#ce61c8"/>
            <path d="M389 58 V60 A11 11 0 0 0 411 60 V58 M400 71 V78"
                  fill="none" stroke="#ce61c8" stroke-width="3" stroke-linecap="round"/>
        </svg>
        <p class="thumbs-hint">아래 녹음 버튼을 누르거나 텍스트로 질문해 주세요.</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("question", clear_on_submit=True):
        recording = st.audio_input("음성으로 질문하기")
        question = st.text_input("또는 텍스트로 질문하기")
        submitted = st.form_submit_button("보내기")

    with st.expander("출발 시각 계산", expanded=True):
        defaults = st.session_state.get(
            "departure_defaults", {"대중교통": 35, "자가용": 30, "buffer": 10}
        )
        with st.form("departure_calculator"):
            transport = st.radio("이동수단", ["대중교통", "자가용"], horizontal=True)
            arrival_date = st.date_input("목표 도착 날짜", value=datetime.now(KST).date())
            arrival = st.time_input("목표 도착 시각", value=time(9, 0), step=60)
            calculated = st.form_submit_button("출발 시각 계산")
        if calculated:
            travel = defaults[transport]
            buffer = defaults["buffer"]
            arrival_at = datetime.combine(arrival_date, arrival, tzinfo=KST)
            departure = arrival_at - timedelta(minutes=travel + buffer)
            prefix = "전날 " if departure.date() < arrival_at.date() else ""
            st.session_state.departure_result = (
                departure,
                f"**{prefix}{departure:%H:%M} 출발**",
                f"목표 {arrival:%H:%M} · {transport} 평소 {travel}분 · 여유 {buffer}분",
            )
            if st.session_state.get("departure_alerts_started") is not None:
                st.session_state.departure_alerts_started = datetime.now(KST)
            st.session_state.pop("departure_last_alert", None)

    with st.expander("지각 연락 초안"):
        with st.form("late_message"):
            recipient = st.text_input("받는 분 호칭", value="팀장님", max_chars=40)
            delay = st.number_input("예상 지각 시간 (분)", 1, 720, 10)
            drafted = st.form_submit_button("초안 만들기")
        if drafted:
            greeting = f"{recipient.strip()}, 안녕하세요." if recipient.strip() else "안녕하세요."
            st.session_state.late_draft = (
                f"{greeting} 김대리입니다. 오늘 출근이 약 {delay}분 늦어질 것 같아 "
                "미리 연락드립니다. 도착 시간이 달라지면 다시 말씀드리겠습니다. 감사합니다."
            )
        if "late_draft" in st.session_state:
            st.code(st.session_state.late_draft, language=None)

elif messages:
    st.markdown("#### 최근 질문")
    st.write(messages[-2]["content"])
    with st.expander("✦ 자세한 답변", expanded=True):
        st.markdown(messages[-1]["content"])
    if len(messages) > 2:
        with st.expander("◷ 이전 대화 기록"):
            for message in messages[:-2]:
                st.chat_message(message["role"]).markdown(message["content"])
else:
    st.info("Speak에서 질문을 보내면 여기에 답변이 표시됩니다.")

show_departure_reminders()

if submitted:
    if not question.strip() and recording is None:
        st.warning("질문을 입력하거나 녹음해 주세요.")
        st.stop()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        st.error("OPENAI_API_KEY를 설정해 주세요.")
        st.stop()
    client = OpenAI(api_key=api_key, timeout=60)

    try:
        if not question.strip():
            question = client.audio.transcriptions.create(
                model="whisper-1",
                file=("question.wav", recording.getvalue(), "audio/wav"),
            ).text
    except OpenAIError:
        st.error("음성 변환에 실패했습니다. API 설정을 확인하거나 텍스트로 질문해 주세요.")
        st.stop()

    if not question.strip():
        st.warning("녹음에서 질문을 인식하지 못했습니다.")
        st.stop()

    with st.spinner("답변을 준비하고 있습니다..."):
        try:
            result = client.responses.create(
                model="gpt-4.1-mini",
                instructions=(
                    "당신은 직장인 김대리의 한국어 출근 준비 비서입니다. "
                    "사용자를 김대리님이라고 부르고 결론부터 간단하게 답하세요. "
                    "일정과 준비물을 정리하고, 요청하면 정중한 지각 연락 초안을 작성하세요. "
                    "메시지를 실제로 전송했다고 말하지 마세요. "
                    "출발 시각을 물으면 목표 도착 시각, 평소 소요시간, 여유 시간을 확인하고 "
                    "Speak의 출발 시각 계산 기능을 안내하세요. 현재 교통 상태를 추측하지 마세요."
                ),
                input=[*messages[-10:], {"role": "user", "content": question}],
            )
            answer = result.output_text or "답변을 받지 못했습니다. 다시 질문해 주세요."
        except OpenAIError:
            st.error("답변을 받지 못했습니다. API 키, 모델 접근 권한 또는 사용 한도를 확인해 주세요.")
            st.stop()

    messages.extend([
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ])
    st.session_state.show_latest_answer = True
    st.rerun()
