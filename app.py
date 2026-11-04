
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import streamlit as st
from openai import OpenAI, OpenAIError

st.set_page_config(page_title="ThumbsUp AI", page_icon="👍🏻", layout="wide")

st.title("Thumbs Up, Your Professional AI Voice Assistant")

st.write("당신만의 AI Voice Assistant ThumbsUp입니다.\n무엇이든 음성으로 질문해주세요.")

with st.sidebar:
    mode = st.radio("답변 방식", ["교통 공지 검색", "일반 상담"])
    st.caption("공개된 교통 공지를 확인합니다. 경로별 실시간 소요시간과 열차 도착 시각은 지도나 교통정보 서비스에서 확인하세요.")

    st.subheader("출퇴근 프로필")
    with st.form("commute_profile"):
        region = st.text_input("지역", placeholder="예: 서울")
        home_station = st.text_input("집 근처 역 또는 동네", placeholder="예: 합정역")
        work_station = st.text_input("회사 근처 역 또는 동네", placeholder="예: 삼성역")
        subway = st.text_input("자주 타는 노선", placeholder="예: 2호선")
        road = st.text_input("자주 지나는 도로", placeholder="예: 올림픽대로")
        if st.form_submit_button("프로필 저장"):
            st.session_state.commute_profile = {
                "region": region.strip(),
                "home": home_station.strip(),
                "work": work_station.strip(),
                "subway": subway.strip(),
                "road": road.strip(),
            }
            st.success("이 세션에 프로필을 저장했습니다.")
    st.caption("역이나 동네 이름만 입력하세요. 브리핑을 요청하면 저장한 정보가 검색에 사용됩니다.")


def render_answer(response):
    """검색 출처를 답변의 해당 위치에 클릭 가능한 링크로 붙입니다."""
    parts = []
    for item in response.output:
        if item.type != "message":
            continue
        for content in item.content:
            if content.type != "output_text":
                continue
            answer = content.text
            citations = sorted(
                (entry for entry in content.annotations if entry.type == "url_citation"),
                key=lambda entry: entry.end_index,
                reverse=True,
            )
            for number, citation in reversed(list(enumerate(reversed(citations), start=1))):
                url = citation.url
                if urlsplit(url).scheme in {"http", "https"}:
                    url = url.replace("<", "%3C").replace(">", "%3E")
                    end = citation.end_index
                    answer = answer[:end] + f" [출처 {number}](<{url}>)" + answer[end:]
            parts.append(answer)
    return "\n\n".join(parts)


st.subheader("원클릭 출퇴근 브리핑")
outbound, inbound = st.columns(2)
go_to_work = outbound.button("출근 브리핑")
go_home = inbound.button("퇴근 브리핑")
briefing = "출근" if go_to_work else "퇴근" if go_home else ""
st.markdown("[지도에서 실시간 경로 확인](https://map.kakao.com/)")

st.session_state.setdefault("messages", [])
for message in st.session_state.messages:
    st.chat_message(message["role"]).markdown(message["content"])

with st.form("question", clear_on_submit=True):
    question = st.text_input("김대리님, 무엇을 도와드릴까요?")
    recording = st.audio_input("또는 음성으로 질문하기")
    submitted = st.form_submit_button("보내기")

if submitted or briefing:
    prompt = None
    if briefing:
        profile = st.session_state.get("commute_profile", {})
        if not all(profile.get(field) for field in ("region", "home", "work")):
            st.warning("사이드바에 지역과 집·회사 근처 역 또는 동네를 입력하고 프로필을 저장해 주세요.")
            st.stop()
        origin, destination = profile["home"], profile["work"]
        if briefing == "퇴근":
            origin, destination = destination, origin
        question = f"{briefing} 브리핑"
        prompt = (
            f"김대리의 오늘 {briefing} 브리핑을 작성해 주세요.\n"
            f"지역: {profile['region']}\n출발: {origin}\n도착: {destination}\n"
            f"자주 타는 노선: {profile['subway'] or '미입력'}\n"
            f"자주 지나는 도로: {profile['road'] or '미입력'}\n"
            "프로필을 검색 조건으로 사용해 출발지에서 도착지 방향에 영향을 주는 "
            "오늘의 공개 공지를 확인하세요. 자가용과 지하철을 나눠 작성하세요. "
            "관련 공지마다 영향 구간·방향, 적용 시간, 출처를 표시하세요. "
            "공지 적용 시간이나 방향을 확인할 수 없으면 그 사실을 표시하세요. "
            "확인된 공지가 없으면 '관련 공지를 찾지 못했습니다'라고 표시하고 "
            "마지막에 출발 전에 직접 확인할 항목을 알려주세요."
        )
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

    st.chat_message("user").write(question)
    with st.spinner("출퇴근 정보를 확인하고 있습니다..."):
        now = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M KST")
        search = bool(briefing) or mode == "교통 공지 검색"
        options = {"tools": [{"type": "web_search"}]} if search else {}
        if briefing:
            options["tool_choice"] = "required"
        guidance = (
            "교통 공지나 사고, 통제, 지연을 묻는 경우 웹 검색으로 확인하세요. "
            "공식 교통기관이나 운영기관을 우선하고, 공지의 발표 시각과 적용 시간, 구간을 구분하세요. "
            "지역이나 노선이 불분명하면 한 가지 확인 질문을 하세요. "
            "현재 적용되는 공지를 확인할 수 없다면 확인할 수 없었다고 답하세요."
            if search else
            "일반 상담 모드입니다. 현재 교통 상태는 확인하지 않았다고 안내하세요. "
            "공개 공지가 필요한 경우 교통 공지 검색 모드를 안내하세요."
        )
        try:
            result = client.responses.create(
                model="gpt-4.1-mini",
                instructions=(
                    "당신은 30~40대 직장인 김대리의 한국어 출퇴근 비서입니다. "
                    "사용자를 김대리님이라고 부르고 결론부터 간단하게 답하세요. "
                    f"현재 한국 시각은 {now}입니다. {guidance} "
                    "이전 대화의 교통 상태를 현재 상태로 인용하지 마세요. "
                    "실시간 열차·버스 도착, 경로별 자동차 소요시간과 혼잡도를 추정하지 마세요. "
                    "그 수치가 필요한 경우 사용자가 지도 앱이나 교통기관의 실시간 화면에서 "
                    "어떤 역·방면이나 출발지·목적지를 확인하면 되는지 안내하세요."
                ),
                input=[
                    *(st.session_state.messages[-10:] if not briefing else []),
                    {"role": "user", "content": prompt or question},
                ],
                **options,
            )
            answer = render_answer(result) or "답변을 받지 못했습니다. 다시 질문해 주세요."
        except OpenAIError:
            st.error("답변을 받지 못했습니다. API 키, 모델 접근 권한 또는 사용 한도를 확인해 주세요.")
            st.stop()

    st.chat_message("assistant").markdown(answer)
    st.session_state.messages.extend([
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ])
