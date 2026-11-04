
import json
import os
from urllib.parse import urlencode
from urllib.request import urlopen
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


WORK_END_ALERTS = (
    (10, "공유할 내용이나 인수인계가 있는지 확인하세요."),
    (5, "작업을 저장하고 퇴근 준비를 마무리하세요."),
    (0, "김대리님, 설정한 퇴근 시각이에요."),
)


@st.fragment(run_every="1s")
def show_reminders(plan_key, title, event, alerts):
    started_key = f'{plan_key}_alerts_started'
    last_key = f'{plan_key}_last_alert'
    plan = st.session_state.get(plan_key)
    if not plan:
        return

    departure, label, details = plan
    now = datetime.now(KST)
    remaining = max(0, int((departure - now).total_seconds() + 0.999))
    minutes, seconds = divmod(remaining, 60)

    with st.container(border=True):
        st.subheader(title)
        st.markdown(f"## {label.strip('*')}")
        st.caption(details)
        if now < departure:
            st.metric(f"{event}까지", f"{minutes:02d}:{seconds:02d}")
        else:
            st.write(f"{event} 시각이 되었어요.")

        started = st.session_state.get(started_key)
        if started is None:
            if now < departure and st.button(f"{event} 알림 시작", key=f"{plan_key}_start"):
                st.session_state[started_key] = datetime.now(KST)
                st.rerun(scope="app")
        elif st.button(f"{event} 알림 끄기", key=f"{plan_key}_stop"):
            st.session_state.pop(started_key, None)
            st.session_state.pop(last_key, None)
            st.rerun(scope="app")

        lines = []
        latest_due = None
        for offset, message in alerts:
            scheduled = departure - timedelta(minutes=offset)
            name = f"{offset}분 전" if offset else f"{event} 시각"
            if started is not None and started <= scheduled <= now:
                custom = st.session_state.get(f"{plan_key}_spoken_{offset}")
                latest_due = (scheduled, custom[0] if custom else message, custom)
            if started is not None and scheduled < started:
                status = " · 건너뜀"
            elif scheduled <= now:
                status = " · 지남"
            else:
                status = ""
            lines.append(f"{scheduled:%m/%d %H:%M} {name}{status}")
        st.caption("  |  ".join(lines))

        if latest_due and st.session_state.get(last_key) != latest_due[0]:
            st.session_state[last_key] = latest_due[0]
            if (now - latest_due[0]).total_seconds() < 60:
                st.toast(latest_due[1], icon="🔔")
        if latest_due and (now - latest_due[0]).total_seconds() < 60:
            st.warning(latest_due[1])
            custom = latest_due[2]
            voice = (custom[1], "audio/mpeg") if custom else None
            if voice is None and latest_due[0] == departure:
                voice = st.session_state.get(f"{plan_key}_voice")
            if voice:
                audio_bytes, audio_format = voice
                st.audio(audio_bytes, format=audio_format, autoplay=True)

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
            st.session_state.pop("departure_result_alerts_started", None)
            st.session_state.pop("departure_result_last_alert", None)
            st.success("출퇴근 프로필을 저장했어요.")

@st.cache_data(ttl=900, show_spinner=False)
def load_seoul_forecast():
    params = urlencode({
        "latitude": 37.5665,
        "longitude": 126.9780,
        "timezone": "Asia/Seoul",
        "hourly": "temperature_2m,precipitation_probability",
        "forecast_days": 7,
    })
    with urlopen(f"https://api.open-meteo.com/v1/forecast?{params}", timeout=5) as response:
        return json.load(response)["hourly"]


def show_commute_weather(plan_key):
    with st.container(border=True):
        st.markdown("#### 🌦️ 날씨와 강수 확률")
        plan = st.session_state.get(plan_key)
        planned_at = plan[0] if plan else datetime.now(KST)
        basis = "일정 기준" if plan else "현재 시간대 · 일정 설정 전"
        hour = planned_at.replace(minute=0, second=0, microsecond=0)
        # 강수 확률은 해당 정각 직전 한 시간의 값입니다.
        rain_hour = hour + timedelta(hours=1)
        try:
            forecast = load_seoul_forecast()
            hours = forecast["time"]
            if hour.strftime("%Y-%m-%dT%H:%M") not in hours:
                st.info("설정한 시각은 현재 서울 예보 범위에 없어요.")
                return
            i = hours.index(hour.strftime("%Y-%m-%dT%H:%M"))
            rain_slot = rain_hour.strftime("%Y-%m-%dT%H:%M")
            temperature = forecast["temperature_2m"][i]
            rain = forecast["precipitation_probability"][hours.index(rain_slot)] if rain_slot in hours else None
        except (OSError, ValueError, KeyError, TypeError, IndexError):
            st.info("날씨 예보를 가져오지 못했어요. 잠시 뒤 다시 확인해 주세요.")
            return

        st.caption(f"서울 · {planned_at:%m/%d %H:%M} · {basis}")
        temp_col, rain_col = st.columns(2)
        temp_col.metric(f"기온 · {hour:%H:%M}", f"{temperature:g} °C" if temperature is not None else "—")
        rain_col.metric(
            f"강수 확률 · {hour:%H:%M}–{rain_hour:%H:%M}",
            f"{rain:g}%" if rain is not None else "—",
        )
        if rain is not None and rain > 40:
            st.warning("☔ 강수 확률이 40%를 넘어요. 우산을 챙기세요!")
        st.caption("출처 · [Open-Meteo](https://open-meteo.com/)")


def show_voice_settings(plan_key):
    voice_key = f"{plan_key}_voice"
    with st.expander("🎙️ 미래의 나에게 알람"):
        st.caption("정각에 재생할 한마디를 녹음하거나 음성 파일로 올리세요.")
        with st.form(f"{plan_key}_voice_form", clear_on_submit=True):
            recording = st.audio_input("직접 녹음", key=f"{plan_key}_recording")
            upload = st.file_uploader(
                "또는 음성 파일 올리기", type=["mp3", "wav"], key=f"{plan_key}_upload"
            )
            saved = st.form_submit_button("알림 음성 저장")
        if saved:
            source = upload if upload is not None else recording
            if source is None or source.size == 0:
                st.warning("녹음하거나 음성 파일을 올려 주세요.")
            elif source.size > 5 * 1024 * 1024:
                st.warning("5MB 이하의 음성을 사용해 주세요.")
            else:
                audio_format = "audio/mpeg" if source.name.lower().endswith(".mp3") else "audio/wav"
                st.session_state[voice_key] = (source.getvalue(), audio_format)
                st.success("알림 음성을 저장했어요.")
        if st.button("저장한 음성 지우기", key=f"{plan_key}_remove_voice",
                     disabled=voice_key not in st.session_state):
            st.session_state.pop(voice_key, None)
        if voice_key in st.session_state:
            st.caption("미리 듣기")
            audio_bytes, audio_format = st.session_state[voice_key]
            st.audio(audio_bytes, format=audio_format)


def show_spoken_alert_settings(plan_key, event, alerts, *, include_overtime=False):
    with st.expander("🔊 시점별 텍스트 음성 알림"):
        st.caption("문구를 입력하거나 UTF-8 TXT 파일을 올리세요. 저장한 음성은 알림 시각에 재생돼요.")
        slots = [
            (f"{plan_key}_spoken_{offset}", f"{offset}분 전" if offset else f"{event} 정각")
            for offset, _ in alerts
        ]
        if include_overtime:
            slots.append(("work_end_overtime_voice", "야근 확정 시 · 일정 저장 즉시"))
        for slot, title in slots:
            st.markdown(f"**{title}**")
            saved = st.session_state.get(slot)
            with st.form(f"{slot}_form", clear_on_submit=True):
                text = st.text_area("읽을 문구", max_chars=300, key=f"{slot}_text")
                uploaded = st.file_uploader("또는 TXT 파일 올리기", type=["txt"], key=f"{slot}_file")
                generate = st.form_submit_button("음성 만들고 저장")
            if generate:
                try:
                    if uploaded is not None and not text.strip():
                        if uploaded.size > 4096:
                            raise ValueError
                        text = uploaded.getvalue().decode("utf-8-sig")
                    text = text.strip()
                    if not 1 <= len(text) <= 300:
                        st.warning("1~300자의 문구를 입력하거나 올려 주세요.")
                    elif text == (saved[0] if saved else None):
                        st.info("같은 문구의 음성이 이미 저장돼 있어요.")
                    elif not os.getenv("OPENAI_API_KEY"):
                        st.warning("음성을 만들려면 OPENAI_API_KEY가 필요해요.")
                    else:
                        with st.spinner("알림 음성을 만들고 있어요..."):
                            client = OpenAI(timeout=30)
                            speech = client.audio.speech.create(
                                model="tts-1", voice="nova", input=text, response_format="mp3",
                            )
                            saved = (text, speech.content)
                            st.session_state[slot] = saved
                        st.success("이 시점의 음성 알림을 저장했어요.")
                except ValueError:
                    st.warning("4KB 이하의 UTF-8 TXT 파일을 올려 주세요.")
                except OpenAIError:
                    st.error("음성을 만들지 못했어요. API 키와 사용 한도를 확인해 주세요.")
            if saved:
                if st.button("이 시점 음성 지우기", key=f"{slot}_delete"):
                    st.session_state.pop(slot, None)
                else:
                    st.caption("저장한 문구 · 미리 듣기")
                    st.text(saved[0])
                    st.audio(saved[1], format="audio/mpeg")


commute_tab, work_tab = st.tabs(["출근", "퇴근"])
with work_tab:
    with st.expander("퇴근·야근 알림 설정"):
        with st.form("work_end_schedule"):
            work_status = st.radio("근무 상태", ["정상 퇴근", "야근 확정", "야근 중 · 퇴근 시각 미정"])
            work_date = st.date_input("퇴근 날짜", value=datetime.now(KST).date())
            work_time = st.time_input("퇴근 시각", value=time(18, 0), step=60)
            st.caption("퇴근 시각 미정을 선택하면 날짜와 시각은 사용하지 않습니다.")
            save_work_end = st.form_submit_button("퇴근 일정 저장")

        if save_work_end:
            st.session_state.pop("work_end_result_last_alert", None)
            if work_status == "야근 중 · 퇴근 시각 미정":
                st.session_state.pop("work_end_result", None)
                st.session_state.pop("work_end_result_alerts_started", None)
                st.session_state.work_end_pending = True
            else:
                end_at = datetime.combine(work_date, work_time, tzinfo=KST)
                st.session_state.work_end_result = (
                    end_at,
                    f"**{end_at:%m/%d %H:%M} 퇴근 예정**",
                    f"{work_status} · 한국 시간",
                )
                st.session_state.work_end_pending = False
                if st.session_state.get("work_end_result_alerts_started") is not None:
                    st.session_state.work_end_result_alerts_started = datetime.now(KST)

    if st.session_state.get("work_end_pending"):
        st.info("야근 중 · 퇴근 시각 미정. 새 시각을 저장하면 퇴근 알림을 다시 시작할 수 있어요.")
    show_reminders("work_end_result", "퇴근 계획", "퇴근", WORK_END_ALERTS)
    show_commute_weather("work_end_result")
    show_spoken_alert_settings(
        "work_end_result", "퇴근", WORK_END_ALERTS, include_overtime=True,
    )
    if save_work_end and work_status == "야근 확정":
        st.markdown(
            """
            <style>
            .overtime-blast {
                position: fixed; inset: 0; z-index: 100000;
                display: grid; place-items: center; pointer-events: none;
                background: radial-gradient(circle, #ffbf69ee 0%, #b53c23dc 45%, #221122dd 100%);
                color: white; text-align: center; font-size: clamp(2rem, 9vw, 6rem);
                font-weight: 800; animation: overtime-fade 2.3s ease-out forwards;
            }
            .overtime-blast span { animation: overtime-pop .55s ease-out both; }
            @keyframes overtime-pop {
                from { transform: scale(.35); }
                to { transform: scale(1); }
            }
            @keyframes overtime-fade {
                0%, 55% { opacity: 1; }
                100% { opacity: 0; visibility: hidden; }
            }
            @media (prefers-reduced-motion: reduce) {
                .overtime-blast { animation-timing-function: steps(1, end); }
                .overtime-blast span { animation: none; }
            }
            </style>
            <div class="overtime-blast" aria-hidden="true"><span>💣 💥<br>야근 확정!</span></div>
            """,
            unsafe_allow_html=True,
        )
        st.warning("야근이 확정됐어요. 새 퇴근 일정을 저장했습니다.")
        overtime_voice = st.session_state.get("work_end_overtime_voice")
        if overtime_voice:
            text, audio = overtime_voice
            st.text(text)
            st.audio(audio, format="audio/mpeg", autoplay=True)

    show_voice_settings("work_end_result")

    with st.container(border=True):
        st.markdown("**🏁 퇴근 도장**")
        today = datetime.now(KST).date()
        stamp = st.session_state.get("work_end_stamp")
        stamped_today = stamp is not None and stamp[0] == today
        if st.button("오늘 업무 종료", disabled=stamped_today):
            plan = st.session_state.get("work_end_result")
            overtime = st.session_state.get("work_end_pending") or (
                plan is not None and plan[2].startswith("야근 확정")
            )
            stamp = (today, "연장전 종료" if overtime else "오늘도 무사 퇴근")
            st.session_state.work_end_stamp = stamp
            st.rerun()
        if stamped_today:
            st.success(f"🏁 {stamp[1]} · {stamp[0]:%m/%d}")

    with st.expander("📦 내일의 나에게 인수인계"):
        with st.form("work_handoff_form", clear_on_submit=True):
            note = st.text_input("다음 출근 때 제일 먼저 할 일", max_chars=200)
            saved = st.form_submit_button("인수인계 메모 저장")
        if saved:
            if note.strip():
                st.session_state.next_work_handoff = note.strip()
                st.success("출근 탭에 메모를 남겼어요.")
            else:
                st.warning("남길 일을 한 줄 입력해 주세요.")
        if st.session_state.get("next_work_handoff"):
            st.caption("저장한 메모")
            st.text(st.session_state.next_work_handoff)
        st.caption("메모는 현재 앱 세션에 보관됩니다.")


with commute_tab:
    departure_card = st.container()
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
            if st.session_state.get("departure_result_alerts_started") is not None:
                st.session_state.departure_result_alerts_started = datetime.now(KST)
            st.session_state.pop("departure_result_last_alert", None)
    with departure_card:
        show_reminders("departure_result", "출근 계획", "출발", DEPARTURE_ALERTS)
    show_commute_weather("departure_result")
    show_spoken_alert_settings("departure_result", "출발", DEPARTURE_ALERTS)

    handoff = st.session_state.get("next_work_handoff")
    if handoff:
        with st.container(border=True):
            st.markdown("**📦 다음 출근에 볼 인수인계**")
            st.text(handoff)
            if st.button("메모 확인 완료"):
                st.session_state.pop("next_work_handoff", None)
                st.rerun()


st.divider()
st.subheader("음성 비서")

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
                    "일정과 준비물을 간단히 정리하세요. "
                    "메시지를 실제로 전송했다고 말하지 마세요. "
                    "출발 시각을 물으면 목표 도착 시각, 평소 소요시간, 여유 시간을 확인하고 "
                    "출근 탭의 출발 시각 계산 기능을 안내하세요. 현재 교통 상태를 추측하지 마세요."
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
