
import hashlib  # 업로드한 회의록이 변경되었는지 확인
import html  # 사용자 입력을 웹 화면에 안전하게 표시
import os  # 환경변수에 저장된 인증정보 읽기
import re  # 답변의 첫 줄에서 표시용 문장 추출
import smtplib  # Gmail SMTP 연결
from email.message import EmailMessage  # 한글 이메일 작성

import streamlit as st  # 웹앱 화면 구성
from openai import OpenAI  # OpenAI API 호출


# 1. 페이지 및 스타일 -----------------------------------------------------------
st.set_page_config(page_title="Thumbs Up | 음성 AI 비서", page_icon="👍", layout="wide", initial_sidebar_state="collapsed")  # 기본 화면 설정

st.markdown("""
<style>
/* 시안의 밝은 바탕과 보라색 포인트를 앱 전체에 적용합니다. */
:root, .stApp, [data-testid="stAppViewContainer"] {
  color-scheme: light !important;
  --primary-color: #8464f5; --background-color: #fdfcff;
  --secondary-background-color: #f6f4fd; --text-color: #22263a;
  --border-color: #eae7f3;
}
.stApp { background: radial-gradient(ellipse at 38% 27%, #f6f4ff 0, #fdfcff 42%, #ffffff 80%) !important; color: #22263a !important; }
[data-testid="stHeader"] { display: none !important; }
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], #MainMenu, [data-testid="stToolbar"] { display: none !important; }
.stMainBlockContainer, .block-container { max-width: 1536px !important; padding: 1.25rem 2.6rem 3rem !important; }
.stApp p, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: #26293d; }
.stApp, .stApp button, .stApp input, .stApp textarea { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans KR", "Malgun Gothic", sans-serif; }
.stApp [data-testid="stVerticalBlock"] { gap: 1rem; }
.stApp [data-testid="stHorizontalBlock"] { gap: 2rem; }
.top-brand { display: flex; align-items: center; gap: .6rem; color: #76758b; font-size: .75rem; font-weight: 600; letter-spacing: .02em; }
.top-brand b { color: #49445f; font-size: .88rem; letter-spacing: -.02em; }
.brand-mini { width: 24px; height: 24px; color: #8a6bf6; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; background: #a792ef; display: inline-block; margin-left: .4rem; }
.st-key-topbar { margin-bottom: .25rem; }
.st-key-panel_switch button { background: rgba(255,255,255,.9) !important; border: 1px solid #e9e6f2 !important; color: #77718f !important; border-radius: 30px !important; min-height: 36px !important; padding: .3rem .8rem !important; box-shadow: 0 3px 10px #3c265205; }
.st-key-panel_switch button p { color: #716888 !important; font-size: .78rem !important; font-weight: 500; white-space: nowrap; }
.st-key-workspace { max-width: 1080px; margin: 0 auto; }
.hero { text-align: center; padding: .15rem 0 .3rem; }
.brand-symbol { width: 74px; height: 35px; margin: 0 auto .6rem; display: block; filter: drop-shadow(0 4px 8px #c7b9f840); }
.hero-title { font-size: 2.16rem !important; line-height: 1.28 !important; letter-spacing: -.055em !important; font-weight: 760 !important; padding: 0 !important; margin: 0 !important; color: #25283b !important; }
.hero-title span { margin-left: .55rem; font-weight: 450; font-size: 1.33rem; letter-spacing: -.045em; }
.hero p { color: #8a879c !important; font-size: .91rem; margin: .55rem 0 0; font-weight: 400; }
.st-key-attachment { max-width: 340px; margin: 0 auto; }
.st-key-attachment [data-testid="stExpander"] { background: #ffffffcc !important; border: 1px solid #e9e5f5 !important; border-radius: 24px !important; box-shadow: 0 3px 10px #3d2c6e07; }
.st-key-attachment summary { min-height: 35px !important; padding: .35rem .85rem !important; color: #706586 !important; }
.st-key-attachment summary p { font-size: .78rem !important; font-weight: 500; color: #706586 !important; }
.st-key-attachment summary svg { color: #9b83de !important; }
.st-key-attachment [data-testid="stExpanderDetails"] { padding: .3rem .7rem .7rem; }
.stApp [data-testid="stFileUploaderDropzone"] { background: #faf8ff !important; border: 1px dashed #ded6f3 !important; padding: .7rem !important; border-radius: 15px !important; }
.stApp [data-testid="stFileUploaderDropzone"] * { color: #8e82a7 !important; }
.stApp [data-testid="stFileUploaderDropzone"] button { background: white !important; border: 1px solid #e8e1f4 !important; border-radius: 12px !important; }
.stApp [data-testid="stFileUploaderDropzoneInstructions"] { font-size: .72rem !important; }
.document-chip { display: flex; align-items: center; justify-content: center; gap: .45rem; font-size: .76rem; color: #796498; background: #f6f1fe; border: 1px solid #ece5f8; border-radius: 24px; padding: .45rem .8rem; width: fit-content; max-width: 90%; margin: -.35rem auto .1rem; overflow-wrap: anywhere; }
.document-chip svg { width: 15px; height: 15px; flex: 0 0 auto; }
.question-card { background: #ffffffed; border: 1px solid #efedf7; border-radius: 23px; padding: 1.25rem 1.7rem 1.35rem; text-align: center; box-shadow: 0 10px 38px #65528b08; min-height: 126px; display: flex; flex-direction: column; justify-content: center; }
.question-label { display: flex; align-items: center; justify-content: center; gap: .45rem; color: #8a7ea5; font-size: .76rem; margin-bottom: .65rem; }
.question-label svg { color: #9771fb; width: 17px; height: 17px; }
.question-text { font-size: clamp(1.05rem, 1.5vw, 1.48rem); line-height: 1.65; font-weight: 650; letter-spacing: -.045em; color: #29283d; white-space: pre-wrap; overflow-wrap: anywhere; }
.st-key-voice_stage { position: relative; padding: .55rem 0 .15rem; }
.voice-wave { position: absolute; top: 14px; left: 4%; width: 92%; height: 110px; pointer-events: none; opacity: .9; }
.voice-wave svg { width: 100%; height: 100%; }
.st-key-voice_stage [data-testid="stVerticalBlock"] { gap: .55rem; }
.st-key-voice_recorder { position: relative; z-index: 1; margin: 0 auto; max-width: 440px; }
.st-key-voice_recorder [data-testid="stAudioInput"] > div:last-child { height: 110px !important; background: transparent !important; border: 0 !important; padding: 0 !important; overflow: visible !important; justify-content: center !important; }
.st-key-voice_recorder [data-testid="stAudioInput"] > div:last-child > div:has(> span > button[data-testid="stAudioInputActionButton"]) { padding: 0 !important; margin: 0 !important; gap: 15px !important; }
.st-key-voice_recorder [data-testid="stAudioInput"] > div:last-child > div:has(> [data-testid="stAudioInputWaveSurfer"]) { display: none !important; }
.st-key-voice_recorder:has(button[aria-label="Reset"]) [data-testid="stAudioInput"] > div:last-child > div:has(> [data-testid="stAudioInputWaveSurfer"]) { display: block !important; max-width: 190px; font-size: .76rem; color: #9a7b9e; }
.st-key-voice_recorder [data-testid="stAudioInputWaveformTimeCode"] { display: none; color: #9b80ae !important; background: transparent !important; font-size: .7rem !important; }
.st-key-voice_recorder [data-testid="stAudioInputActionButton"][aria-label="Record"], .st-key-voice_recorder [data-testid="stAudioInputActionButton"][aria-label="Stop recording"], .st-key-voice_recorder [data-testid="stAudioInputActionButton"][aria-label="Reset"] { width: 96px !important; height: 96px !important; min-height: 96px !important; padding: 25px !important; border-radius: 50% !important; color: #9167ff !important; background: linear-gradient(145deg,#ffffff,#fdfbff) !important; border: 1px solid #f5f0ff !important; box-shadow: 0 0 0 7px #f4f0ff80, 0 0 30px #bba5ff7a, 0 7px 18px #9481cb20 !important; }
.st-key-voice_recorder [data-testid="stAudioInputActionButton"] svg { width: 40px !important; height: 40px !important; }
.st-key-voice_recorder [data-testid="stAudioInputActionButton"][aria-label="Record"]:hover { background: #faf6ff !important; box-shadow: 0 0 0 8px #eee7ff90, 0 0 40px #bba5ff9a !important; }
.st-key-voice_recorder [data-testid="stAudioInputActionButton"][aria-label="Stop recording"] { color: #d47ab6 !important; box-shadow: 0 0 0 8px #faeafa90, 0 0 36px #d2a2ee90 !important; }
.st-key-voice_recorder:has(button[aria-label="Stop recording"]) [data-testid="stAudioInputWaveformTimeCode"], .st-key-voice_recorder:has(button[aria-label="Play"]) [data-testid="stAudioInputWaveformTimeCode"], .st-key-voice_recorder:has(button[aria-label="Pause"]) [data-testid="stAudioInputWaveformTimeCode"] { display: inline !important; position: absolute; bottom: -8px; left: 50%; transform: translateX(-50%); margin: 0 !important; }
.st-key-voice_recorder button[aria-label="Play"], .st-key-voice_recorder button[aria-label="Pause"] { width: 33px !important; height: 33px !important; padding: 4px !important; background: #f7f0ff !important; color: #a283cc !important; border: 1px solid #e6daf7 !important; border-radius: 50% !important; }
.st-key-voice_recorder button[aria-label="Play"] svg, .st-key-voice_recorder button[aria-label="Pause"] svg { width: 22px !important; height: 22px !important; }
.voice-hint { text-align: center; color: #8d879f; font-size: .78rem; line-height: 1.6; margin: 0; }
.voice-hint b { color: #837292; font-weight: 500; }
.st-key-voice_submit { max-width: 260px; margin: 0 auto; }
.st-key-typed_question { max-width: 590px; margin: -.15rem auto .3rem; }
.stApp [data-testid="stChatInput"] { background: #ffffffed !important; border: 1px solid #eae6f4 !important; border-radius: 25px !important; box-shadow: 0 3px 14px #56407604; }
.stApp [data-testid="stChatInput"] > div, .stApp [data-testid="stChatInput"] > div > div { background: transparent !important; border: 0 !important; border-radius: 25px !important; }
.stApp [data-testid="stChatInput"] textarea { background: transparent !important; color: #3b344e !important; font-size: .83rem !important; }
.stApp [data-testid="stChatInput"] textarea::placeholder { color: #aaa1b9 !important; opacity: 1 !important; }
.stApp [data-testid="stChatInputSubmitButton"] { color: #9579df !important; background: #f4efff !important; }
.st-key-answer_card, .st-key-risk_card { background: #ffffffed; border: 1px solid #e8e4f3; border-radius: 22px; padding: 1.05rem 1.3rem; box-shadow: 0 7px 23px #58407606; }
.st-key-answer_card [data-testid="stVerticalBlock"], .st-key-risk_card [data-testid="stVerticalBlock"] { gap: .65rem; }
.card-title { display: flex; align-items: center; gap: .6rem; font-size: .82rem; color: #7f758f; font-weight: 500; }
.icon-bubble { width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; color: #956aff; background: #f6f0ff; flex: 0 0 auto; }
.icon-bubble svg { width: 20px; height: 20px; }
.answer-preview { font-size: 1.02rem; line-height: 1.7; font-weight: 600; color: #373048; padding: .1rem .1rem .2rem 2.6rem; letter-spacing: -.025em; overflow-wrap: anywhere; }
.answer-preview.empty { color: #aca4b9; font-weight: 400; font-size: .86rem; }
.stApp audio { width: 100%; height: 42px; color-scheme: light !important; border-radius: 20px; }
.stApp audio::-webkit-media-controls-panel { background: #f6f3fe; }
.st-key-answer_card [data-testid="stExpander"], .st-key-risk_card [data-testid="stExpander"] { background: #f7f4fd !important; border: 0 !important; border-radius: 15px !important; }
.stApp summary { color: #6e5c87 !important; }
.st-key-answer_card summary p, .st-key-risk_card summary p { color: #766387 !important; font-size: .8rem !important; }
.stApp [data-testid="stExpanderDetails"] { color: #423951 !important; }
.st-key-answer_card [data-testid="stExpanderDetails"] p, .st-key-risk_card [data-testid="stExpanderDetails"] p { font-size: .85rem; line-height: 1.8; }
.risk-heading { display: flex; align-items: center; gap: .7rem; margin-bottom: .3rem; }
.risk-heading strong { font-size: .97rem; letter-spacing: -.03em; color: #3b314c; }
.risk-heading p { font-size: .76rem; color: #94879e !important; margin: .2rem 0 0; }
.stApp [data-testid="stButton"] button, .stApp [data-testid="stFormSubmitButton"] button { background: #fff !important; border: 1px solid #e7e0f1 !important; border-radius: 13px !important; color: #7a668d !important; min-height: 39px; transition: background .2s, box-shadow .2s, border-color .2s; }
.stApp [data-testid="stButton"] button p, .stApp [data-testid="stFormSubmitButton"] button p { color: inherit !important; font-size: .82rem; }
.stApp [data-testid="stButton"] button:hover { border-color: #bda8f1 !important; background: #faf7ff !important; box-shadow: 0 4px 13px #a28acb12; }
.stApp [data-testid="stButton"] button[kind="primary"], .stApp [data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"] { background: linear-gradient(115deg,#a181f7,#8665ee) !important; border: 1px solid #9a7af1 !important; color: white !important; box-shadow: 0 4px 14px #9977e61c; }
.st-key-settings_panel { background: #ffffffed; border: 1px solid #eeebf6; border-radius: 24px; padding: 1.5rem 1.45rem; min-height: 730px; box-shadow: 0 9px 35px #64508007; }
.st-key-settings_panel [data-testid="stVerticalBlock"] { gap: .7rem; }
.panel-title { display: flex; align-items: center; gap: .65rem; font-size: 1.08rem; font-weight: 700; color: #2e2d42; margin-bottom: .2rem; letter-spacing: -.025em; }
.panel-title svg { width: 22px; height: 22px; color: #514562; }
.panel-section { display: flex; align-items: center; gap: .7rem; font-size: .86rem; font-weight: 650; color: #3d354d; margin: .25rem 0 .15rem; }
.panel-section svg { width: 18px; height: 18px; color: #82748d; }
.st-key-settings_panel hr { margin: .65rem 0 !important; border-color: #ede9f4 !important; }
.st-key-settings_panel [data-testid="stWidgetLabel"] p { font-size: .8rem !important; color: #645b73 !important; font-weight: 400; }
.stApp [data-testid="stCheckbox"]:has(input[role="switch"]) label { gap: .65rem; padding: .22rem 0; }
.stApp [data-testid="stCheckbox"]:has(input[role="switch"]) label > div:first-of-type { background: #e6e0ee !important; }
.stApp [data-testid="stCheckbox"]:has(input[role="switch"]) label[data-selected="true"] > div:first-of-type { background: linear-gradient(100deg,#9b80f7,#8160ee) !important; }
.stApp [data-testid="stCheckbox"]:has(input[role="switch"]) label > div:first-of-type > div { background: #ffffff !important; box-shadow: 0 1px 4px #58446c18; }
.stApp [data-testid="stSelectbox"] [role="group"] { background: #fff !important; border: 1px solid #e5dfee !important; color: #76627f !important; border-radius: 13px !important; min-height: 42px !important; }
.stApp [data-testid="stSelectbox"] input { background: transparent !important; color: #716079 !important; font-size: .8rem !important; }
.stApp [data-testid="stSelectbox"] button { background: transparent !important; color: #a18db0 !important; }
.stApp [data-testid="stSelectbox"] svg { color: #a18db0 !important; }
.react-aria-Popover, .react-aria-ListBox, [role="listbox"], [role="option"] { background: #fff !important; color: #62506d !important; }
[role="option"][data-focused="true"], [role="option"][data-selected="true"] { background: #f4efff !important; color: #82629e !important; }
.stApp [data-baseweb="select"] > div { background: #fff !important; border-color: #e5dfee !important; color: #76627f !important; border-radius: 13px !important; min-height: 42px !important; }
.stApp [data-baseweb="select"] span { color: #716079 !important; font-size: .8rem; }
.stApp [data-baseweb="select"] svg { color: #a18db0 !important; }
[data-baseweb="popover"] [role="listbox"], [data-baseweb="popover"] li { background: #fff !important; color: #62506d !important; }
[data-baseweb="popover"] li:hover { background: #f6f1ff !important; }
.stApp [data-baseweb="input"], .stApp [data-baseweb="textarea"] { background: #fff !important; border-color: #e8e0f0 !important; border-radius: 13px !important; }
.stApp [data-testid="stTextInputRootElement"], .stApp [data-testid="stTextAreaRootElement"] { background: #fff !important; border: 1px solid #e8e0f0 !important; border-radius: 13px !important; }
.stApp [data-testid="stTextInputRootElement"] input, .stApp [data-testid="stTextAreaRootElement"] textarea { background: transparent !important; }
.stApp input, .stApp textarea { color: #42364d !important; caret-color: #9674e8; }
.st-key-settings_panel [data-testid="stCaptionContainer"] p { font-size: .69rem !important; color: #aaa0b5 !important; line-height: 1.7; }
.stApp [data-testid="stCheckbox"] label:has(input:checked) > span { background: #9674f0 !important; border-color: #9674f0 !important; }
.stApp [data-testid="stAlert"] { border-radius: 14px !important; }
.st-key-email_area [data-testid="stExpander"] { background: #fff !important; border: 1px solid #e9e3f2 !important; border-radius: 20px !important; }
.st-key-email_area [data-testid="stForm"] { border: 0 !important; }
.stApp :focus-visible { outline-color: #b49ae9 !important; }
@media (min-width: 1100px) { .st-key-settings_panel { position: sticky; top: 2rem; } }
@media (max-width: 1000px) { .stMainBlockContainer, .block-container { padding: 1.25rem 1.3rem 2rem !important; } .stApp [data-testid="stHorizontalBlock"] { gap: 1.15rem; } .st-key-settings_panel { padding: 1.25rem 1rem; } .hero-title { font-size: 1.9rem !important; } .hero-title span { font-size: 1.1rem; } }
@media (max-width: 640px) { .stMainBlockContainer, .block-container { padding: .8rem 1rem 2rem !important; } .st-key-topbar [data-testid="stHorizontalBlock"] { flex-wrap: nowrap; } .st-key-topbar [data-testid="stColumn"] { min-width: 0 !important; } .top-brand { font-size: 0; gap: .35rem; } .top-brand b { font-size: .8rem; } .hero { padding-top: .6rem; } .hero-title { font-size: 1.75rem !important; } .hero-title span { font-size: 1rem; margin-left: .35rem; } .hero p { font-size: .75rem; } .question-card { padding: 1.1rem; } .question-text { font-size: 1.06rem; } .st-key-settings_panel { min-height: auto; } .answer-preview { padding-left: .15rem; font-size: .94rem; } .st-key-answer_card, .st-key-risk_card { padding: 1rem; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }
@media (max-width: 640px) { .st-key-topbar [data-testid="stColumn"]:first-child { flex: 1 1 auto !important; } .st-key-topbar [data-testid="stColumn"]:last-child { flex: 0 0 112px !important; min-width: 112px !important; } }
</style>

""", unsafe_allow_html=True)  # 흰색·연보라색 테마와 카드 디자인 적용

# [답변 디자인 시작] 이 구간은 API 호출과 독립된 CSS·표시 함수입니다.
# 다른 앱으로 옮길 때 html, re, streamlit as st를 함께 불러오면 됩니다.
ANSWER_DESIGN_CSS = """
<style>
/* 내용의 종류에 따른 색상입니다. 위험도 등급이나 사실 판정을 뜻하지 않습니다. */
.st-key-answer_detail, .st-key-risk_detail {
  --tu-ink: #3d4158;
  --tu-blue-bg: linear-gradient(110deg, #e8efff, #f0edff);
  --tu-blue-ink: #40558e;
  --tu-lilac-bg: linear-gradient(110deg, #ede7ff, #f6efff);
  --tu-lilac-ink: #6b4ea4;
  --tu-rose-bg: linear-gradient(110deg, #ffe7f0, #fff1f6);
  --tu-rose-ink: #a33f6c;
  --tu-amber-bg: linear-gradient(110deg, #ffeedb, #fff7eb);
  --tu-amber-ink: #936026;
  --tu-mint-bg: linear-gradient(110deg, #e4f4ef, #f0faf6);
  --tu-mint-ink: #2c7160;
  --tu-neutral-bg: linear-gradient(110deg, #eff0f6, #f7f7fb);
  --tu-neutral-ink: #62687c;
}
.st-key-answer_card [data-testid="stExpander"],
.st-key-risk_card [data-testid="stExpander"] {
  background: linear-gradient(135deg, #fff, #fcfbff) !important;
  border: 1px solid #eeebf7 !important;
  border-radius: 16px !important;
}
.st-key-answer_card [data-testid="stExpanderDetails"],
.st-key-risk_card [data-testid="stExpanderDetails"] {
  padding: .6rem 1.05rem 1rem !important;
}
.st-key-answer_detail [data-testid="stMarkdownContainer"],
.st-key-risk_detail [data-testid="stMarkdownContainer"] {
  color: var(--tu-ink) !important;
  font-size: .9rem;
  line-height: 1.95;
  letter-spacing: -.018em;
  overflow-wrap: anywhere;
}
.st-key-answer_detail [data-testid="stMarkdownContainer"] p,
.st-key-answer_detail [data-testid="stMarkdownContainer"] li,
.st-key-risk_detail [data-testid="stMarkdownContainer"] p,
.st-key-risk_detail [data-testid="stMarkdownContainer"] li {
  color: var(--tu-ink) !important;
  font-size: .9rem !important;
  line-height: 1.95 !important;
}
.st-key-answer_detail [data-testid="stMarkdownContainer"] p,
.st-key-risk_detail [data-testid="stMarkdownContainer"] p { margin: 0 0 .7rem; }
.st-key-answer_detail [data-testid="stMarkdownContainer"] p:last-child,
.st-key-risk_detail [data-testid="stMarkdownContainer"] p:last-child { margin-bottom: 0; }
.st-key-answer_detail [data-testid="stMarkdownContainer"] ol,
.st-key-answer_detail [data-testid="stMarkdownContainer"] ul { padding-left: 1.45rem; margin: .55rem 0 .85rem; }
.st-key-answer_detail [data-testid="stMarkdownContainer"] li { padding: .18rem 0 .18rem .12rem; }
.st-key-answer_detail [data-testid="stMarkdownContainer"] li::marker { color: #a392cc; font-weight: 600; }
.st-key-answer_detail [data-testid="stMarkdownContainer"] li > p,
.st-key-risk_detail [data-testid="stMarkdownContainer"] li > p { margin-bottom: .3rem; }
.st-key-answer_detail [data-testid="stMarkdownContainer"] h1,
.st-key-answer_detail [data-testid="stMarkdownContainer"] h2,
.st-key-answer_detail [data-testid="stMarkdownContainer"] h3,
.st-key-answer_detail [data-testid="stMarkdownContainer"] h4,
.st-key-risk_detail [data-testid="stMarkdownContainer"] h1,
.st-key-risk_detail [data-testid="stMarkdownContainer"] h2,
.st-key-risk_detail [data-testid="stMarkdownContainer"] h3,
.st-key-risk_detail [data-testid="stMarkdownContainer"] h4 {
  font-size: 1rem !important; line-height: 1.6 !important;
  font-weight: 680 !important; margin: 1.05rem 0 .55rem !important; padding: 0 !important;
}
.st-key-answer_detail .tu-mark, .st-key-risk_detail .tu-mark {
  display: inline;
  padding: .14em .56em .18em;
  border-radius: .72em;
  font-weight: 650;
  font-size: .94em;
  line-height: inherit;
  -webkit-box-decoration-break: clone;
  box-decoration-break: clone;
  background: var(--tu-blue-bg);
  color: var(--tu-blue-ink) !important;
  box-shadow: inset 0 0 0 1px #ffffff70;
}
.st-key-answer_detail .tu-mark--blue, .st-key-risk_detail .tu-mark--blue { background: var(--tu-blue-bg); color: var(--tu-blue-ink) !important; }
.st-key-answer_detail .tu-mark--lilac, .st-key-risk_detail .tu-mark--lilac { background: var(--tu-lilac-bg); color: var(--tu-lilac-ink) !important; }
.st-key-answer_detail .tu-mark--rose, .st-key-risk_detail .tu-mark--rose { background: var(--tu-rose-bg); color: var(--tu-rose-ink) !important; }
.st-key-answer_detail .tu-mark--amber, .st-key-risk_detail .tu-mark--amber { background: var(--tu-amber-bg); color: var(--tu-amber-ink) !important; }
.st-key-answer_detail .tu-mark--mint, .st-key-risk_detail .tu-mark--mint { background: var(--tu-mint-bg); color: var(--tu-mint-ink) !important; }
.st-key-answer_detail .tu-mark--neutral, .st-key-risk_detail .tu-mark--neutral { background: var(--tu-neutral-bg); color: var(--tu-neutral-ink) !important; }
.st-key-risk_detail [data-testid="stMarkdownContainer"] > ol,
.st-key-risk_detail [data-testid="stMarkdownContainer"] > ul {
  margin: .2rem 0 .4rem; padding-left: 0; list-style: none;
  display: grid; gap: .65rem;
}
.st-key-risk_detail [data-testid="stMarkdownContainer"] > ol > li,
.st-key-risk_detail [data-testid="stMarkdownContainer"] > ul > li {
  background: linear-gradient(110deg, #ffffff, #fdfbff);
  border: 1px solid #eeebf5; border-radius: 13px;
  padding: .65rem .85rem; box-shadow: 0 2px 7px #6f4b8704;
}
.st-key-risk_detail [data-testid="stMarkdownContainer"] > ol > li > ul,
.st-key-risk_detail [data-testid="stMarkdownContainer"] > ul > li > ul { padding-left: 1.25rem; margin: .35rem 0 0; }
.st-key-risk_detail [data-testid="stMarkdownContainer"] blockquote {
  border-left: 3px solid #dfd4fa; background: #faf8ff;
  border-radius: 0 10px 10px 0; padding: .45rem .8rem; margin: .55rem 0;
}
@media (max-width: 640px) {
  .st-key-answer_card [data-testid="stExpanderDetails"], .st-key-risk_card [data-testid="stExpanderDetails"] { padding: .4rem .7rem .8rem !important; }
  .st-key-answer_detail [data-testid="stMarkdownContainer"] p, .st-key-answer_detail [data-testid="stMarkdownContainer"] li,
  .st-key-risk_detail [data-testid="stMarkdownContainer"] p, .st-key-risk_detail [data-testid="stMarkdownContainer"] li { font-size: .86rem !important; }
  .st-key-answer_detail .tu-mark, .st-key-risk_detail .tu-mark { padding-left: .43em; padding-right: .43em; }
}
</style>
"""  # 답변 영역에만 적용하는 파스텔 색상·배지·여백


def answer_label_tone(label):  # 제목에 실제 들어 있는 단어로 색상만 선택
    compact = re.sub(r"\s+", "", label)  # 띄어쓰기가 달라도 같은 제목으로 처리
    if any(word in compact for word in ("회의록의근거", "회의록근거", "원문근거", "근거")):  # 출처·근거 제목
        return "neutral"  # 중립적인 회색 계열
    if "담당자" in compact and any(word in compact for word in ("확인", "미정", "누락", "불명확", "미지정")):  # 담당자 확인 항목
        return "amber"  # 부드러운 살구색
    if any(word in compact for word in ("완료기준", "업무범위", "승인기준", "산출물")):  # 범위와 완료 기준
        return "lilac"  # 연보라색
    if any(word in compact for word in ("확인", "미정", "누락", "모호", "불명확", "미확정", "추가논의", "주의", "리스크", "위험")):  # 확인할 내용
        return "rose"  # 연분홍색
    if any(word in compact for word in ("예산", "금액", "비용")):  # 금액 관련 제목
        return "mint"  # 옅은 민트색
    if any(word in compact for word in ("일정", "기한", "마감", "출시일", "다음회의", "날짜")):  # 일정 관련 제목
        return "lilac"  # 연보라색
    return "blue"  # 담당 업무 등 일반 핵심 항목은 파랑·보라 계열


def answer_badge(label):  # 원래 제목의 글자는 유지하고 표시 태그만 추가
    tone = answer_label_tone(label)  # 내용 유형에 맞는 색상 선택
    safe_label = html.escape(label, quote=False)  # 답변에 들어 있는 HTML을 실행하지 않음
    return f'<strong class="tu-mark tu-mark--{tone}">{safe_label}</strong>'  # 앱이 만든 강조 태그만 사용


def decorate_answer_segment(segment):  # 코드가 아닌 일반 문장 안의 굵은 제목을 강조
    parts, cursor = [], 0  # 변환한 조각과 읽은 위치 준비
    pattern = r"(?<!\\)(\*\*|__)(?=\S)([^\n]+?)(?<=\S)\1"  # Markdown 굵은 글씨만 찾기
    for match in re.finditer(pattern, segment):  # 원래 제목을 순서대로 확인
        parts.append(html.escape(segment[cursor:match.start()], quote=False))  # 앞쪽 문장은 그대로 표시
        label = match.group(2)  # 굵게 지정된 원문
        if re.search(r"[\[\]*_`$]", label):  # 링크·수식 등 복합 서식은 원래 Markdown 유지
            parts.append(html.escape(match.group(0), quote=False))  # 지원하지 않는 서식을 임의로 바꾸지 않음
        else:  # 일반 텍스트 제목이면
            parts.append(answer_badge(label))  # 파스텔 강조 적용
        cursor = match.end()  # 읽은 위치 갱신
    parts.append(html.escape(segment[cursor:], quote=False))  # 마지막 일반 문장 추가
    return "".join(parts)  # 원래 글자와 순서를 유지한 문장 반환


def decorate_answer_inline(line):  # 인라인 코드·수식·자동 링크는 강조 대상에서 제외
    protected = r"(`+)(?:[^`]|(?!\1)`)*?\1(?!`)|(?<!\\)\$[^\n$]+\$|<(?:https?://|mailto:)[^<>\s]+>"  # 보호할 원문
    parts, cursor = [], 0  # 결과와 처리 위치 준비
    for match in re.finditer(protected, line):  # 보호 구간을 차례로 확인
        parts.append(decorate_answer_segment(line[cursor:match.start()]))  # 일반 문장만 꾸미기
        parts.append(match.group(0))  # 코드·수식·링크는 원문 보존
        cursor = match.end()  # 다음 처리 위치
    parts.append(decorate_answer_segment(line[cursor:]))  # 나머지 일반 문장 처리
    return "".join(parts)  # 꾸민 한 줄 반환


def format_answer_markdown(text):  # API 결과를 바꾸지 않고 화면용 사본만 꾸미기
    labels = ("제가 맡은 업무", "담당 업무", "확인이 필요한 사항", "확인할 사항", "추가 확인 사항", "확인할 질문", "회의록의 근거", "회의록 근거", "근거", "출시일", "홍보 채널", "예산", "다음 회의", "담당자", "기한", "마감일", "완료 기준", "업무 범위", "일정")  # 일반 텍스트 제목도 지원
    options = "|".join(re.escape(label).replace(r"\ ", r"\s*") for label in labels)  # 제목의 띄어쓰기 허용
    label_pattern = re.compile(r"^([ \t]*(?:(?:[-+*]|\d+[.)])\s+)?)(" + options + r")([ \t]*[:：])")  # 줄 앞 제목만 찾기
    output, fence, fence_size, math_block = [], "", 0, False  # 여러 줄 코드·수식 상태
    for line in str(text).splitlines(keepends=True):  # 줄바꿈과 문단 순서 보존
        fence_match = re.match(r"^ {0,3}(`{3,}|~{3,})", line)  # 코드 블록 시작·끝 확인
        if fence:  # 코드 블록 안에서는
            output.append(line)  # 글자와 서식을 그대로 유지
            if fence_match and fence_match.group(1)[0] == fence and len(fence_match.group(1)) >= fence_size:  # 닫는 구분자
                fence = ""  # 코드 블록 종료
            continue  # 강조하지 않음
        if fence_match:  # 새 코드 블록이면
            fence, fence_size = fence_match.group(1)[0], len(fence_match.group(1))  # 구분자 기억
            output.append(line)  # 시작 줄 보존
            continue  # 코드 내용은 다음 반복에서 처리
        if line.strip() == "$$":  # 여러 줄 수식 구분자이면
            math_block = not math_block  # 수식 구간 상태 전환
            output.append(line)  # 구분자 보존
            continue  # 수식을 강조하지 않음
        if math_block or (re.match(r"^(?: {4}|\t)", line) and not re.match(r"^\s*(?:[-+*]|\d+[.)])\s+", line)):  # 수식·들여쓴 코드
            output.append(line)  # 원문 보존
            continue  # 코드·수식 처리를 Markdown에 맡김
        quote_match = re.match(r"^( {0,3}(?:>[ \t]*)+)", line)  # 인용문 표시 기호 보존
        quote_prefix = quote_match.group(1) if quote_match else ""  # 원래 인용 표시
        body = line[len(quote_prefix):]  # 인용문 안쪽 텍스트
        label_match = label_pattern.match(body)  # 굵게 쓰지 않은 항목 제목 확인
        if label_match:  # '출시일:' 같은 제목이면
            prefix, label, colon = label_match.groups()  # 목록 기호·제목·콜론 분리
            decorated = prefix + answer_badge(label) + colon + decorate_answer_inline(body[label_match.end():])  # 제목만 강조
        else:  # 일반 Markdown 문장이면
            decorated = decorate_answer_inline(body)  # 원래 굵은 제목을 찾아 강조
        output.append(quote_prefix + decorated)  # 원래 줄 순서에 맞게 저장
    return "".join(output)  # 원문 답변은 별도로 유지


def render_answer_presentation(text, kind="answer"):  # 답변·리스크 영역에서 같은 디자인 사용
    container_key = "risk_detail" if kind == "risk" else "answer_detail"  # CSS 적용 범위 구분
    with st.container(key=container_key):  # 앱의 다른 영역에 색상이 번지지 않게 범위 지정
        if re.search(r"<[!/?A-Za-z]", str(text)):  # HTML 예제·자동 링크가 포함된 복합 답변이면
            st.markdown(text)  # 원래의 안전한 Markdown 표시 방식과 코드 예제를 보존
        else:  # 앱이 생성한 강조 태그만 포함되는 일반 답변이면
            st.markdown(format_answer_markdown(text), unsafe_allow_html=True)  # 보호 처리한 화면용 사본 표시


st.markdown(ANSWER_DESIGN_CSS, unsafe_allow_html=True)  # 답변 전용 디자인 등록
# [답변 디자인 끝]


# 2. 비밀정보와 기본 상태 ------------------------------------------------------
def get_secret(name):  # 환경변수 또는 Streamlit Secrets에서 인증정보 읽기
    if os.getenv(name):  # 코랩에서 환경변수를 전달했다면
        return os.getenv(name)  # 환경변수 사용
    try:  # 배포한 Streamlit 앱이라면
        return st.secrets.get(name, "")  # Secrets에서 읽기
    except Exception:  # 설정 파일이 아직 없어도 화면은 보여주기
        return ""  # 인증정보 없음


api_key = get_secret("OPENAI_API_KEY")  # OpenAI API 키 확인
client = OpenAI(api_key=api_key) if api_key else None  # API 키가 있을 때만 클라이언트 생성

initial_state = {  # 앱 화면과 대화에 필요한 상태 초기값
    "panel_open": True,  # 오른쪽 설정 패널은 처음에 열린 상태
    "use_meeting": True,  # 회의록 분석 기능 활성화
    "enable_risk": True,  # 업무 리스크 점검 기능 활성화
    "enable_email": False,  # 이메일 발송 영역은 처음에 감춤
    "use_tts": True,  # 음성으로 답변 듣기 활성화
    "voice": "nova",  # 기본 TTS 목소리
    "keep_history": True,  # 같은 세션에서 대화 문맥 유지
    "turns": [],  # 질문과 답변 기록
    "last_question": "",  # 최근 사용자 질문
    "last_answer": "",  # 최근 GPT 답변
    "last_audio": None,  # 최근 TTS 음성 바이트
    "risk_result": "",  # 업무 리스크 분석 결과
    "document_hash": "",  # 현재 업로드된 문서 식별자
    "recorder_count": 0,  # 녹음 완료 후 새 녹음기를 표시하기 위한 번호
    "mail_body": "",  # 이메일 전송 본문
}  # 기본 상태 정의 완료
for name, value in initial_state.items():  # 각 상태를 확인해
    if name not in st.session_state:  # 처음 실행할 때만
        st.session_state[name] = value  # 초기값 저장


def to_text(upload):  # 업로드 파일을 한국어 문자열로 변환
    if upload is None:  # 파일이 없다면
        return ""  # 빈 문자열 반환
    contents = upload.getvalue()  # 파일 내용 읽기
    if len(contents) > 1_000_000:  # 1MB 이상은 비용·처리 부담을 피하기 위해 제한
        st.warning("회의록은 1MB 이하 TXT 파일을 사용해 주세요.")  # 용량 안내
        return ""  # 처리하지 않음
    for enc in ("utf-8-sig", "cp949"):  # UTF-8과 한국어 Windows 인코딩 순서로 시도
        try:  # 지정한 인코딩으로 변환
            return contents.decode(enc)  # 변환에 성공한 문자열 반환
        except UnicodeDecodeError:  # 다른 인코딩이라면
            continue  # 다음 형식 시도
    st.error("회의록을 읽지 못했습니다. UTF-8 TXT 파일을 사용해 주세요.")  # 읽기 오류 안내
    return ""  # 처리하지 않음


def ask_gpt(question, meeting_text):  # 기존 미션 3의 GPT 호출을 웹앱용으로 재사용
    instruction = "당신은 음성 AI 개인비서 Thumbs Up입니다. 간결하고 정확한 한국어 존댓말로 답변하세요. 회의록에 없는 사실은 만들어내지 마세요."  # AI 역할
    if meeting_text and st.session_state.use_meeting:  # 회의록이 있고 분석 기능이 켜졌다면
        instruction += "\n[참고 회의록]\n" + meeting_text  # 회의록을 GPT에 함께 전달
    history = st.session_state.turns[-8:] if st.session_state.keep_history else []  # 최근 대화만 참고
    messages = [{"role": "system", "content": instruction}] + history + [{"role": "user", "content": question}]  # API 입력 구성
    result = client.responses.create(model="gpt-4o-mini", input=messages)  # GPT에 질문하고 응답 생성
    return result.output_text  # 답변 글자만 반환


def analyze_risks(meeting_text):  # 기존 미션 3의 프롬프트를 확장한 업무 리스크 분석
    instruction = "당신은 회의록의 업무 수행상 불확실성을 점검하는 비서입니다. 근거 없는 리스크를 만들지 마세요."  # 분석 역할
    prompt = f"""아래 회의록에서 업무 수행에 필요한 정보의 누락이나 모호함을 점검하세요.
검사 기준: (1) 담당자 미정 (2) 기한 누락·모호 (3) 완료 기준·업무 범위 불명확.
각 항목은 '확인이 필요한 사항 / 회의록의 근거 / 확인할 질문' 순서로 3줄 이내로 작성하세요.
문제가 없으면 '추가 확인이 필요한 사항을 찾지 못했습니다'라고 적으세요.
회의록에서 확인되는 내용과 추정은 구분하고, 임의의 인물·날짜를 만들지 마세요.
[회의록]\n{meeting_text}"""  # 업무 리스크 점검 요청
    result = client.responses.create(model="gpt-4o-mini", input=[{"role": "system", "content": instruction}, {"role": "user", "content": prompt}])  # GPT에 점검 요청
    return result.output_text  # 분석 결과 반환


def send_gmail(receiver, subject, body):  # 미션 1에서 배운 SMTP 이메일 발송 기능
    sender = get_secret("GMAIL_ADDRESS")  # 발신자 주소 읽기
    password = get_secret("GMAIL_APP_PASSWORD")  # Gmail 앱 비밀번호 읽기
    if not sender or not password:  # 인증정보가 없다면
        raise ValueError("GMAIL_ADDRESS 및 GMAIL_APP_PASSWORD 설정이 필요합니다.")  # 오류 안내
    message = EmailMessage()  # 이메일 객체 생성
    message["From"] = sender  # 발신자 지정
    message["To"] = receiver  # 수신자 지정
    message["Subject"] = subject  # 제목 지정
    message.set_content(body)  # 본문 지정
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as smtp:  # Gmail 보안 연결
        smtp.login(sender, password)  # Gmail 인증
        smtp.send_message(message)  # 실제 이메일 발송


def save_setting(name):  # 오른쪽 패널을 닫아도 선택한 설정을 기억하기 위한 콜백
    st.session_state[name] = st.session_state[f"_widget_{name}"]  # 위젯 값을 별도 영구 세션 값에 복사


def preference_toggle(label, name):  # 설정 패널을 다시 열 때도 이전 선택을 복구하는 토글
    widget_name = f"_widget_{name}"  # 화면 위젯 전용 임시 키
    if widget_name not in st.session_state:  # 패널을 다시 열어 위젯이 새로 생겼다면
        st.session_state[widget_name] = st.session_state[name]  # 저장해 둔 선택값을 복구
    st.toggle(label, key=widget_name, on_change=save_setting, args=(name,))  # 토글 조작 시 설정값 저장


# 3. 화면 아이콘과 오른쪽 패널 -------------------------------------------------
def ui_icon(name):  # 외부 이미지 파일 없이 동일한 선 모양의 아이콘 만들기
    paths = {  # 각 기능을 나타내는 SVG 도형
        "mic": '<rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8"/>',
        "settings": '<path d="m9 3 .6-1h4.8l.6 1 .6 2 2 .9 2.2-.4 2.4 4.2-1.4 1.7v2.2l1.4 1.7-2.4 4.2-2.2-.4-2 .9-.6 2h-6l-.6-2-2-.9-2.2.4-2.4-4.2L3 13.6v-2.2L1.6 9.7 4 5.5l2.2.4 2-.9Z"/><circle cx="12" cy="12" r="3"/>',
        "wave": '<path d="M3 10v4M7 6v12M12 2v20M17 7v10M21 10v4"/>',
        "user": '<circle cx="12" cy="7" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2Z"/>',
        "shield": '<path d="M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6Z"/><path d="M12 7v6M12 16h.01"/>',
        "bot": '<rect x="3" y="7" width="18" height="14" rx="4"/><path d="M12 7V3M9 3h6M7 12v3M17 12v3M9 18h6M1 11v5M23 11v5"/>',
        "file": '<path d="M14 2H5v20h14V7Z"/><path d="M14 2v6h5M8 12h8M8 16h6"/>',
    }  # 아이콘 목록 완성
    return f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths[name]}</svg>'  # HTML에 넣을 아이콘 반환


def section_heading(name, text):  # 설정 묶음 제목을 같은 모양으로 표시
    st.markdown(f'<div class="panel-section">{ui_icon(name)}<span>{text}</span></div>', unsafe_allow_html=True)  # 작은 아이콘과 제목 표시


with st.container(key="topbar"):  # 상단 로고와 설정 열기·닫기 버튼
    brand_column, button_column = st.columns([7, 1.6], vertical_alignment="center")  # 상단 두 영역 배치
    with brand_column:  # 왼쪽의 작은 브랜드 표시
        st.markdown(f'<div class="top-brand"><span class="brand-mini">{ui_icon("wave")}</span><b>Thumbs Up</b><span class="status-dot"></span><span>Voice AI Assistant</span></div>', unsafe_allow_html=True)  # 얇은 선 아이콘 사용
    with button_column:  # 설정 제어 버튼
        btn_label = "설정 닫기 ×" if st.session_state.panel_open else "설정 열기 ⚙"  # 현재 패널 상태에 맞는 문구
        if st.button(btn_label, use_container_width=True, key="panel_switch"):  # 사용자가 버튼을 누르면
            st.session_state.panel_open = not st.session_state.panel_open  # 열림·닫힘 상태 반전
            st.rerun()  # 설정 공간까지 제거하거나 복구

layout_style = "<style>.st-key-app_layout [data-testid='stHorizontalBlock'] > [data-testid='stColumn']:last-child{display:none!important}.st-key-app_layout [data-testid='stHorizontalBlock'] > [data-testid='stColumn']:first-child{flex:1 1 100%!important;width:100%!important;min-width:0!important}</style>" if not st.session_state.panel_open else "<style></style>"  # 녹음기 위치는 보존하면서 설정 공간만 접기
st.markdown(layout_style, unsafe_allow_html=True)  # 설정을 닫으면 본문에 전체 폭 배정
with st.container(key="app_layout"):  # 설정창 조작 중에도 본문 위젯의 위치 유지
    main_column, setting_column = st.columns([3.25, 1.24], gap="large")  # 본문과 오른쪽 설정창 배치

if st.session_state.panel_open:  # 설정창이 열린 경우에만 내부 기능 표시
    with setting_column:  # 오른쪽 열 안에서
        with st.container(key="settings_panel"):  # 흰색의 둥근 설정 카드
            st.markdown(f'<div class="panel-title">{ui_icon("settings")}<span>설정 및 도구</span></div>', unsafe_allow_html=True)  # 설정창 제목
            st.divider()  # 얇은 구분선
            section_heading("mic", "사용 기능 선택")  # 기능 그룹 제목
            preference_toggle("회의록 분석 (요약·업무 정리)", "use_meeting")  # 기존 회의록 기능 유지
            preference_toggle("업무 리스크 점검", "enable_risk")  # 기존 리스크 기능 유지
            preference_toggle("이메일 작성 및 발송", "enable_email")  # 기존 이메일 기능 유지
            st.divider()  # 그룹 구분
            section_heading("wave", "답변 방식")  # 출력 그룹 제목
            preference_toggle("음성 + 텍스트", "use_tts")  # 끄면 텍스트로만 답변
            st.divider()  # 그룹 구분
            section_heading("user", "음성 설정 (TTS)")  # 음성 그룹 제목
            if "_widget_voice" not in st.session_state:  # 설정창을 다시 열었을 때
                st.session_state["_widget_voice"] = st.session_state.voice  # 이전 음성 선택 복원
            voice_labels = {"nova": "기본 음성 · Nova", "alloy": "다른 음성 · Alloy", "shimmer": "다른 음성 · Shimmer"}  # 음성 선택 표시 이름
            st.selectbox("답변 목소리", list(voice_labels), key="_widget_voice", format_func=lambda value: voice_labels[value], on_change=save_setting, args=("voice",), disabled=not st.session_state.use_tts, label_visibility="collapsed")  # 기존 TTS 음성을 보기 쉬운 이름으로 선택
            st.divider()  # 그룹 구분
            section_heading("settings", "기타 설정")  # 추가 설정 제목
            preference_toggle("대화 문맥 유지", "keep_history")  # 대화 맥락 보존 여부
            if st.button("새 대화 시작", use_container_width=True, key="new_chat"):  # 대화 초기화 요청
                st.session_state.turns = []  # 대화 이력 비우기
                st.session_state.last_question = ""  # 질문 표시 초기화
                st.session_state.last_answer = ""  # 답변 표시 초기화
                st.session_state.last_audio = None  # 답변 음성 초기화
                st.session_state.risk_result = ""  # 분석 결과 초기화
                st.session_state.recorder_count += 1  # 녹음 위젯 초기화
                st.rerun()  # 초기 화면 다시 표시
            st.caption("설정은 현재 브라우저 세션에서 유지됩니다.")  # 설정 보존 범위 안내


# 4. 중앙 음성 화면 ------------------------------------------------------------
with main_column:  # 본문 열에 표시
    with st.container(key="workspace"):  # 본문의 최대 폭과 중앙 정렬
        st.markdown('''<div class="hero"><svg class="brand-symbol" viewBox="0 0 100 44" fill="none" aria-hidden="true"><defs><linearGradient id="brandGradient" x1="8" y1="10" x2="85" y2="35" gradientUnits="userSpaceOnUse"><stop stop-color="#9fdafa"/><stop offset=".48" stop-color="#b09afa"/><stop offset="1" stop-color="#e3bafa"/></linearGradient></defs><path d="M3 24C18 23 23 3 37 4S55 33 70 29s19-15 27-6c-16 1-18 20-34 16S43 16 30 21 14 35 3 24Z" fill="url(#brandGradient)"/><path d="M4 26c13-15 24-8 35-4s20 9 33 5 17-7 24-3c-16 1-18 20-34 15S39 14 27 23 12 32 4 26Z" fill="#c6b1fb" opacity=".32"/></svg><div class="hero-title" role="heading" aria-level="1">Thumbs Up<span>AI 개인비서</span></div><p>음성으로 질문하면, Thumbs Up이 알려드릴게요.</p></div>''', unsafe_allow_html=True)  # 시안의 그라데이션 로고와 차분한 제목

        with st.container(key="attachment"):  # 작은 첨부 메뉴
            with st.expander("회의록 첨부 · TXT", expanded=False):  # 기본 화면에서 큰 업로드 상자를 접어두기
                meeting_file = st.file_uploader("회의록 파일", type=["txt"], key="meeting_file", label_visibility="collapsed")  # 기존 TXT 업로드 유지
                st.caption("분석할 회의록이 있을 때 첨부해 주세요.")  # 간단한 도움말
        meeting_text = to_text(meeting_file) if meeting_file is not None else ""  # 문서 내용 읽기
        document_hash = hashlib.sha256(meeting_text.encode("utf-8")).hexdigest() if meeting_text else ""  # 현재 문서 식별
        if document_hash != st.session_state.document_hash:  # 문서가 바뀌었다면
            st.session_state.document_hash = document_hash  # 문서 식별값 갱신
            st.session_state.risk_result = ""  # 이전 문서 분석 결과 제거
            st.session_state.turns = []  # 다른 문서의 대화가 섞이지 않게 초기화
        if meeting_text:  # 읽은 문서가 있다면
            st.markdown(f'<div class="document-chip">{ui_icon("file")}<span>{html.escape(meeting_file.name)}</span></div>', unsafe_allow_html=True)  # 파일명만 작은 칩으로 표시

        question_text = st.session_state.last_question or "마이크를 눌러 말씀해 주세요"  # 최근 질문 또는 첫 사용 안내
        st.markdown(f'<div class="question-card"><div class="question-label">{ui_icon("mic")}<span>내 말 · 음성 인식 결과</span></div><div class="question-text">{html.escape(question_text)}</div></div>', unsafe_allow_html=True)  # 시안의 흰색 질문 카드

        with st.container(key="voice_stage"):  # 파형과 실제 녹음기를 겹쳐 배치
            st.markdown('''<div class="voice-wave" aria-hidden="true"><svg viewBox="0 0 900 120" preserveAspectRatio="none"><defs><linearGradient id="waveGradient"><stop stop-color="#c8ddff" stop-opacity="0"/><stop offset=".2" stop-color="#b5d6ff" stop-opacity=".55"/><stop offset=".5" stop-color="#c4a0fa" stop-opacity=".7"/><stop offset=".75" stop-color="#f6bce6" stop-opacity=".65"/><stop offset="1" stop-color="#dfc9ff" stop-opacity="0"/></linearGradient></defs><path d="M0 60C110 60 112 43 175 48S275 82 348 64 405 39 450 50 526 77 590 60 667 47 740 56 835 60 900 60C780 67 740 57 675 69S550 80 475 62 410 53 350 66 235 59 170 61 60 60 0 60Z" fill="url(#waveGradient)"/><path d="M0 60C120 58 155 75 245 62S340 47 400 56 485 82 560 65 675 40 745 55 830 61 900 60C805 63 755 77 690 65S600 56 535 66 430 68 360 59 270 73 205 65 80 60 0 60Z" fill="url(#waveGradient)" opacity=".66"/></svg></div>''', unsafe_allow_html=True)  # 정적인 보라·파랑·분홍 파형
            with st.container(key="voice_recorder"):  # 이 안의 실제 마이크 버튼을 둥글게 스타일링
                audio_value = st.audio_input("음성 질문 녹음", key=f"mic_input_{st.session_state.recorder_count}", label_visibility="collapsed")  # Streamlit 기본 녹음 기능 그대로 사용
            st.markdown('<p class="voice-hint">마이크를 눌러 녹음하고, 다시 눌러 마치세요</p>', unsafe_allow_html=True)  # 실제 녹음 조작 안내
            with st.container(key="voice_submit"):  # 녹음했을 때만 전송 버튼 표시
                send_audio = st.button("녹음한 질문 보내기", use_container_width=True, type="primary", key="send_voice") if audio_value is not None else False  # 기존 제출 절차 유지
        typed_question = st.chat_input("또는 글자로 질문해 주세요", key="typed_question")  # 마이크 없이도 질문 가능

        pending_question = None  # 이번에 보낼 질문 초기값
        if send_audio and audio_value is not None:  # 녹음 제출 요청
            if client is None:  # API 키가 없는 경우
                st.error("OPENAI_API_KEY 설정이 필요합니다.")  # 인증 안내
            else:  # 음성 인식 가능
                try:  # 음성 인식 시도
                    with st.spinner("말씀하신 내용을 인식하고 있습니다..."):  # 처리 진행 표시
                        transcript = client.audio.transcriptions.create(model="whisper-1", file=("question.wav", audio_value.getvalue(), "audio/wav"))  # 기존 Whisper 사용
                        pending_question = transcript.text.strip()  # 인식한 질문 추출
                except Exception as error:  # 음성 인식 오류
                    st.error(f"음성 인식 중 오류: {error}")  # 오류 안내
        elif typed_question:  # 글자 질문을 제출했다면
            pending_question = typed_question.strip()  # 글자 질문 저장

        if pending_question:  # 유효한 질문이 있다면
            if client is None:  # 인증정보가 없다면
                st.error("OPENAI_API_KEY 설정이 필요합니다.")  # 인증 안내
            else:  # 답변 생성 가능
                try:  # GPT 및 TTS 호출 시도
                    with st.spinner("Thumbs Up이 답변을 준비하고 있습니다..."):  # 답변 생성 안내
                        answer = ask_gpt(pending_question, meeting_text)  # 기존 GPT 답변 함수 사용
                        speech_bytes = None  # 음성 결과 초기화
                        if st.session_state.use_tts and answer:  # 음성 답변이 켜져 있다면
                            try:  # 음성 변환 시도
                                speech = client.audio.speech.create(model="gpt-4o-mini-tts", voice=st.session_state.voice, input=answer[:3500])  # 기존 TTS 사용
                                speech_bytes = speech.content  # 음성 바이트 저장
                            except Exception as error:  # 음성 변환만 실패했다면
                                st.warning(f"텍스트 답변은 준비됐지만 음성 생성에 실패했습니다: {error}")  # 텍스트 답변은 유지
                        st.session_state.last_question = pending_question  # 질문 갱신
                        st.session_state.last_answer = answer  # 답변 갱신
                        st.session_state.last_audio = speech_bytes  # 음성 결과 갱신
                        st.session_state.turns.extend([{"role": "user", "content": pending_question}, {"role": "assistant", "content": answer}])  # 대화 기록 추가
                        st.session_state.mail_body = answer  # 이메일 초안 유지
                        st.session_state.recorder_count += 1  # 다음 녹음을 위한 위젯 초기화
                    st.rerun()  # 질문·답변 화면 갱신
                except Exception as error:  # 답변 생성 오류
                    st.error(f"답변 생성 중 오류: {error}")  # 오류 안내

        with st.container(key="answer_card"):  # 시안의 답변 카드
            st.markdown(f'<div class="card-title"><span class="icon-bubble">{ui_icon("bot")}</span><span>Thumbs Up의 답변</span></div>', unsafe_allow_html=True)  # 답변 영역 제목
            if st.session_state.last_answer:  # 생성한 답변이 있다면
                first_line = next((line.strip().strip("#*- ") for line in st.session_state.last_answer.splitlines() if line.strip()), "답변이 준비됐습니다.")  # 첫 줄을 미리보기로 사용
                preview = first_line[:108] + ("…" if len(first_line) > 108 else "")  # 미리보기 길이 제한
                st.markdown(f'<div class="answer-preview">{html.escape(preview)}</div>', unsafe_allow_html=True)  # 한 줄 미리보기
                if st.session_state.use_tts and st.session_state.last_audio:  # 답변 음성이 있다면
                    st.audio(st.session_state.last_audio, format="audio/mp3")  # 음성 재생 컨트롤
                with st.expander("전체 답변 펼치기"):  # 아래 방향 화살표로 전체 답변 확인
                    render_answer_presentation(st.session_state.last_answer)  # 원문 내용을 유지하고 핵심 제목만 강조
            else:  # 아직 질문하기 전이라면
                st.markdown('<div class="answer-preview empty">질문을 보내면 이곳에서 답변을 확인할 수 있습니다.</div>', unsafe_allow_html=True)  # 빈 상태 안내

        if meeting_text and st.session_state.use_meeting and st.session_state.enable_risk:  # 회의록이 있고 리스크 기능이 켜졌을 때만
            with st.container(key="risk_card"):  # 하단의 보조 기능 카드
                st.markdown(f'<div class="risk-heading"><span class="icon-bubble">{ui_icon("shield")}</span><div><strong>업무 리스크 점검</strong><p>담당자, 기한, 업무 범위에서 확인할 사항을 찾습니다.</p></div></div>', unsafe_allow_html=True)  # 리스크 카드 제목
                if st.button("업무 리스크 점검하기", use_container_width=True, key="risk_run"):  # 사용자가 직접 점검 요청
                    if client is None:  # API 키가 없다면
                        st.error("OPENAI_API_KEY 설정이 필요합니다.")  # 인증 안내
                    else:  # 점검 실행 가능
                        try:  # 분석 시도
                            with st.spinner("회의록에서 확인할 사항을 찾고 있습니다..."):  # 진행 표시
                                st.session_state.risk_result = analyze_risks(meeting_text)  # 기존 리스크 분석 함수 사용
                        except Exception as error:  # 분석 오류
                            st.error(f"리스크 분석 중 오류: {error}")  # 오류 안내
                if st.session_state.risk_result:  # 분석 결과가 있으면
                    with st.expander("확인이 필요한 사항", expanded=True):  # 점검 결과 표시
                        render_answer_presentation(st.session_state.risk_result, kind="risk")  # 원문 근거·확인 질문에 동일한 디자인 적용
                        st.caption("분석 결과를 실제 회의록과 대조해 확인해 주세요.")  # 결과 확인 안내

        if st.session_state.enable_email and st.session_state.last_answer:  # 이메일 기능과 답변이 있을 때
            with st.container(key="email_area"):  # 이메일 영역 스타일
                with st.expander("이메일 작성 및 발송"):  # 이메일 양식은 기본적으로 접기
                    st.caption("수신자·제목·본문을 확인하고 발송 버튼을 눌러 주세요.")  # 기존 직접 발송 방식 안내
                    with st.form("email_form"):  # 이메일 작성 양식
                        receiver = st.text_input("받는 사람", value=get_secret("GMAIL_ADDRESS"))  # 기본 수신자 유지
                        mail_subject = st.text_input("제목", value="Thumbs Up AI 비서 답변")  # 기본 제목
                        mail_body = st.text_area("본문", key="mail_body", height=180)  # 기존 답변을 초안으로 사용
                        confirmed = st.checkbox("수신자·제목·본문을 확인했습니다.")  # 전송 전 확인
                        do_send = st.form_submit_button("이메일 발송", type="primary")  # 사용자가 직접 발송 요청
                    if do_send:  # 발송 요청이 있다면
                        if not confirmed:  # 확인하지 않았다면
                            st.warning("내용 확인에 체크한 뒤 발송해 주세요.")  # 발송 중단
                        elif not receiver.strip() or "@" not in receiver:  # 수신자 형식이 맞지 않으면
                            st.warning("올바른 수신자 주소를 입력해 주세요.")  # 주소 안내
                        else:  # 발송 조건 충족
                            try:  # 이메일 발송 시도
                                send_gmail(receiver.strip(), mail_subject.strip(), mail_body)  # 기존 발송 함수 사용
                                st.success("이메일 발송 요청이 완료됐습니다. 수신함에서도 확인해 주세요.")  # 성공 안내
                            except Exception as error:  # 이메일 오류
                                st.error(f"이메일 발송 실패: {error}")  # 오류 안내
