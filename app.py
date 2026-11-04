
import os
from html import escape
from datetime import datetime, timedelta, timezone
from urllib.error import URLError
from urllib.parse import quote, urlsplit
from urllib.request import urlopen
from xml.etree import ElementTree

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
<div class="thumbs-brand"><strong>ThumbsUp AI</strong><span>김대리의 음성 출퇴근 비서</span></div>
""", unsafe_allow_html=True)

with st.sidebar:
    mode = st.radio("답변 방식", ["교통 공지 검색", "일반 상담"])
    st.caption("공개된 교통 공지를 확인합니다. 역별 실시간 열차 도착 정보는 Speak 화면에서 조회할 수 있습니다.")

    st.subheader("출퇴근 프로필")
    with st.form("commute_profile_form"):
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
briefing = ""
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

    outbound, inbound = st.columns(2)
    go_to_work = outbound.button("출근 브리핑", use_container_width=True)
    go_home = inbound.button("퇴근 브리핑", use_container_width=True)
    briefing = "출근" if go_to_work else "퇴근" if go_home else ""
    with st.expander("🚇 실시간 지하철 도착", expanded=True):
        profile = st.session_state.get("commute_profile", {})
        direction = st.radio("탑승 방향", ["출근", "퇴근"], horizontal=True)
        default_station = profile.get("home" if direction == "출근" else "work", "")
        station_input = st.text_input(
            "탑승역 직접 지정 (선택)",
            placeholder=default_station or "예: 충무로역",
        )
        st.caption("직접 지정하지 않으면 저장된 출발역을 조회합니다. 도착 조회에는 OpenAI를 호출하지 않습니다.")
        if st.button("다음 열차 조회"):
            station = (station_input.strip() or default_station).removesuffix("역").strip()
            subway_key = os.getenv("SEOUL_SUBWAY_API_KEY", "").strip()
            if not subway_key:
                st.warning("Streamlit Secrets에 SEOUL_SUBWAY_API_KEY를 등록해 주세요.")
            elif not station:
                st.warning("탑승역을 직접 입력하거나 출퇴근 프로필을 저장해 주세요.")
            else:
                station = "".join(station.split())
                url = (
                    f"https://swopenapi.seoul.go.kr/api/subway/{quote(subway_key, safe='')}"
                    f"/xml/realtimeStationArrival/0/20/{quote(station, safe='')}"
                )
                try:
                    with st.spinner("서울시 열차 도착 정보를 조회하고 있습니다..."):
                        with urlopen(url, timeout=10) as response:
                            arrivals = ElementTree.fromstring(response.read())
                    rows = arrivals.findall("row")
                    if arrivals.findtext("RESULT/code") not in (None, "INFO-000"):
                        st.warning("서울시 API에서 조회를 처리하지 못했습니다. 인증키 종류와 호출 한도를 확인해 주세요.")
                    elif not rows:
                        st.info("도착 정보가 없습니다. 역 이름을 확인하거나 잠시 후 다시 조회해 주세요.")
                    else:
                        st.dataframe(
                            [
                                {
                                    "역": row.findtext("statnNm") or station,
                                    "행선지·방면": row.findtext("trainLineNm") or "—",
                                    "도착 안내": row.findtext("arvlMsg2") or "—",
                                    "정보 생성 시각 (KST)": row.findtext("recptnDt") or "—",
                                }
                                for row in rows
                            ],
                            hide_index=True,
                        )
                        st.caption("출처 · 서울 열린데이터광장. 탑승할 노선과 방면을 확인하세요.")
                except (URLError, OSError, ElementTree.ParseError):
                    st.error("서울시 지하철 도착 정보를 불러오지 못했습니다. 잠시 후 다시 조회해 주세요.")
    with st.expander("🚗 TOPIS 실시간 도로 소통"):
        saved_road = st.session_state.get("commute_profile", {}).get("road", "")
        if saved_road:
            st.write(f"프로필에 저장한 도로: {saved_road}")
        st.caption("TOPIS 도로별 링크 정보에서 확인한 구간 ID를 입력하세요. 같은 도로도 구간과 방향별로 ID가 다릅니다.")
        st.markdown("[도로별 링크 정보](https://data.seoul.go.kr/dataList/OA-13309/A/1/datasetView.do)")
        with st.form("topis_traffic_form"):
            link_id = st.text_input("도로 구간 ID (LINK_ID)").strip()
            lookup_road = st.form_submit_button("도로 소통 조회")
        if lookup_road:
            topis_key = os.getenv("SEOUL_TOPIS_API_KEY", "").strip()
            if not topis_key:
                st.warning("Streamlit Secrets에 SEOUL_TOPIS_API_KEY를 등록해 주세요.")
            elif not (link_id.isascii() and link_id.isdecimal()):
                st.warning("도로 구간 ID를 숫자로 입력해 주세요.")
            else:
                url = (
                    f"http://openapi.seoul.go.kr:8088/{quote(topis_key, safe='')}"
                    f"/xml/TrafficInfo/1/5/{link_id}"
                )
                try:
                    with st.spinner("TOPIS 도로 소통 정보를 조회하고 있습니다..."):
                        with urlopen(url, timeout=10) as response:
                            traffic = ElementTree.fromstring(response.read())
                    code = traffic.findtext("RESULT/CODE")
                    rows = traffic.findall("row")
                    if code == "INFO-200" or (code == "INFO-000" and not rows):
                        st.info("이 구간의 통행 정보가 없습니다. 구간 ID를 확인해 주세요.")
                    elif code != "INFO-000":
                        st.warning("TOPIS가 조회를 처리하지 못했습니다. 일반 인증키와 구간 ID를 확인해 주세요.")
                    else:
                        st.dataframe(
                            [
                                {
                                    "구간 ID": row.findtext("LINK_ID") or link_id,
                                    "통행속도": row.findtext("PRCS_SPD") or "—",
                                    "구간 통과시간": row.findtext("PRCS_TRV_TIME") or "—",
                                }
                                for row in rows
                            ],
                            hide_index=True,
                        )
                        checked_at = datetime.now(timezone(timedelta(hours=9)))
                        st.caption(f"출처 · 서울시 TOPIS | 조회 시각 {checked_at:%H:%M:%S} KST")
                except (OSError, ElementTree.ParseError):
                    st.error("TOPIS 도로 소통 정보를 불러오지 못했습니다. 잠시 후 다시 조회해 주세요.")
    st.markdown("[지도에서 실시간 경로 확인](https://map.kakao.com/)")
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

    messages.extend([
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ])
    st.session_state.show_latest_answer = True
    st.rerun()
