import os
import io
import re
import json
import textwrap
import tempfile
import datetime

import streamlit as st
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import HumanMessage, AIMessage
from langchain_pymupdf4llm import PyMuPDF4LLMLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from operator import itemgetter

# =====================================================================
# 0. 기본 설정
# =====================================================================
st.set_page_config(page_title="AIVLE GUIDE", page_icon="🧭", layout="wide")

# Streamlit Cloud: Secrets에 OPENAI_API_KEY 등록 시 환경변수로 연결
try:
    if "OPENAI_API_KEY" in st.secrets:
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
except Exception:
    pass

CHROMA_DIR = "chroma_db"          # Colab에서 만든 폴더와 같아야 함
COLLECTION = "aivle_docs"         # Colab에서 만든 컬렉션과 같아야 함
LLM_MODEL = "gpt-4o-mini"
EMB_MODEL = "text-embedding-3-small"

# 사용자 구분별 단계(수준) 이름
LEVELS = {
    "지원자": ["탐색 단계", "지원 준비", "합격 후"],
    "교육생": ["초급", "중급", "고급"],
}

# 사용자 구분별 역할(페르소나)
PERSONA = {
    "지원자": (
        "당신은 KT 에이블스쿨 지원을 고민하는 예비 지원자를 돕는 'AIVLE GUIDE'입니다. "
        "지원자의 불안과 궁금증을 공감하며 풀어 주고, 백서에 근거한 정확한 정보로 "
        "'나도 도전해 볼 수 있겠다'는 확신을 주는 따뜻한 선배처럼 답합니다."
    ),
    "교육생": (
        "당신은 KT 에이블스쿨 교육생의 학습·생활을 돕는 'AIVLE GUIDE' 학습 코치입니다. "
        "교육생의 수준에 맞춰 개념을 쉽게 풀고, 지금 바로 실행할 수 있는 학습 행동을 제안하며, "
        "끝까지 완주할 수 있도록 응원하는 든든한 선배처럼 답합니다."
    ),
}

# 답변 길이 조절
LENGTH = {
    "기본": "핵심 결론을 먼저 말한 뒤 필요한 만큼 친절하게 설명하세요(5~10문장 내외, 필요 시 목록 사용).",
    "짧게": "3문장 이내로 핵심만 간결하게 답하세요.",
    "자세히": "단계별로 자세히 설명하고, 예시와 확인 방법, 주의사항까지 충분히 포함하세요.",
}

# 시스템 메시지 (미션 4: 역할 지정 + 문서 기반 + 기수·규정 구분 + 도전 독려)
SYSTEM_TEMPLATE = """{persona}

[사용자 정보]
- 사용자 구분/수준: {level}

[답변 원칙]
1. 반드시 아래 [문서]에 근거해 답합니다. 문서에 없는 내용은 추측하지 말고
   "백서에서 확인되지 않는 내용입니다"라고 밝힌 뒤, 확인할 수 있는 공식 경로(AIVLE-EDU, 담당 매니저, 공식 공고 등)를 안내합니다.
2. 기수·규정 구분: 모집 일정, 지원 자격, 출결, 공가, 훈련장려금, 자부담금 등 운영 규정은
   어느 기수 기준인지(예: "10기 기준") 반드시 밝히고, 다음 기수나 개인 판정에는 다를 수 있으며
   최신 공지·담당자 안내가 우선한다고 덧붙입니다.
3. 정보의 성격을 구분합니다: 「공식 운영 기준」, 「수료생 경험」, 「실천 제안」.
4. 근거가 된 문서 위치를 문장 끝에 (p.N) 형태로 표시합니다.
5. 사용자의 수준에 맞는 용어와 깊이로 설명합니다.
6. 마지막 줄에는 사용자가 다음에 해볼 수 있는 한 가지 행동이나 짧은 응원 한마디를 덧붙입니다.
7. 답변 길이: {length_guide}

[문서]
{context}"""

# 기수·규정 관련 키워드 (답변 하단 주의 배지 표시용)
RULE_KEYWORDS = ["출결", "출석", "지각", "조퇴", "결석", "외출", "공가", "장려금", "모집", "지원 자격",
                 "자격", "일정", "수료", "제적", "자부담", "내일배움", "합격", "선발", "질병"]

# 추천 질문 (사용자 구분 × 수준)
RECOMMENDED = {
    ("지원자", "탐색 단계"): ["에이블스쿨은 어떤 교육과정인가요?",
                          "AI 개발자와 DX 컨설턴트 트랙은 어떻게 다른가요?",
                          "비전공자도 지원해서 잘 따라갈 수 있나요?"],
    ("지원자", "지원 준비"): ["지원서 에세이는 어떻게 준비하면 좋을까요?",
                          "국민내일배움카드는 꼭 필요한가요?",
                          "10기 지원 자격과 모집 일정은 어땠나요?"],
    ("지원자", "합격 후"): ["합격 후 입교 전에 무엇을 확인해야 하나요?",
                        "교육은 하루에 어떤 일정으로 진행되나요?",
                        "입교 전에 미리 공부해 두면 좋은 것은?"],
    ("교육생", "초급"): ["지각·조퇴·외출 기준은 어떻게 되나요?",
                      "비전공자는 복습을 어떻게 하면 좋을까요?",
                      "RAG에서 청킹과 임베딩이 뭔가요?"],
    ("교육생", "중급"): ["RAG 검색 설정을 바꾸면 결과가 어떻게 달라지나요?",
                      "미니프로젝트에서 팀워크는 어떻게 하면 좋을까요?",
                      "훈련장려금은 어떤 기준으로 지급되나요?"],
    ("교육생", "고급"): ["RAG 답변 품질은 어떻게 검증하나요?",
                      "빅프로젝트를 잘 수행한 선배들의 공통점은?",
                      "프로젝트를 포트폴리오로 어떻게 정리하나요?"],
}

SITUATIONS = ["출결·지각·조퇴", "공가·출석 인정", "훈련장려금", "실습·코드 오류",
              "프로젝트·팀워크", "AIVLE-EDU·접속 문제", "기타"]

INTERESTS = ["데이터 분석", "머신러닝", "딥러닝", "RAG·LLM", "클라우드",
             "프로젝트·협업", "취업·포트폴리오"]


# =====================================================================
# 1. RAG 파이프라인 (01번 노트북의 rag_pipeline 구조를 그대로 사용)
# =====================================================================
# 문서 포맷터
def format_docs(docs):
    return "\n\n".join(d.page_content for d in docs)


# 페이지 번호 (PyMuPDF4LLMLoader의 page는 0부터 시작)
def page_of(doc):
    p = doc.metadata.get("page")
    return p + 1 if isinstance(p, int) else "?"


# 출처(페이지)를 붙인 문서 포맷터 — 답변에 (p.N) 표기를 유도
def format_docs_with_page(docs):
    return "\n\n".join(f"[p.{page_of(d)}]\n{d.page_content}" for d in docs)


# RAG 체인 구성 (input만 넣어도 동작, 앱에서는 context·history 등을 추가로 전달)
def build_chain(retriever):
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_TEMPLATE),
        MessagesPlaceholder("history", optional=True),
        ("human", "{input}"),
    ])
    llm = ChatOpenAI(model=LLM_MODEL, temperature=0.2, streaming=True)

    def get_context(x):
        # 앱에서 미리 검색한 문서를 넘기면 그대로 사용 (출처 표시와 같은 문서 사용)
        if x.get("context"):
            return x["context"]
        return format_docs_with_page(retriever.invoke(x["input"]))

    rag_chain = (
        {
            "context": RunnableLambda(get_context),
            "input": itemgetter("input"),
            "history": RunnableLambda(lambda x: x.get("history", [])),
            "persona": RunnableLambda(lambda x: x.get("persona", PERSONA["교육생"])),
            "level": RunnableLambda(lambda x: x.get("level", "교육생 / 초급")),
            "length_guide": RunnableLambda(lambda x: x.get("length_guide", LENGTH["기본"])),
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    return rag_chain


# RAG 파이프라인 함수
def rag_pipeline(filepath, return_retriever=False):

    # PDF 파일 읽기
    loader = PyMuPDF4LLMLoader(filepath)
    docs = loader.load()

    # 텍스트 분할
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        separators=["\n\n", "\n", ".", " ", ""])
    chunks = splitter.split_documents(docs)

    # Embedding 모델
    embedding = OpenAIEmbeddings(model=EMB_MODEL)

    # 벡터저장소 만들기
    vectorstore = Chroma(
        collection_name=COLLECTION,
        embedding_function=embedding,
        persist_directory=CHROMA_DIR
    )

    # 기존 데이터 비우기
    vectorstore.reset_collection()

    # 문서 추가
    _ = vectorstore.add_documents(chunks)

    # 검색기 구성
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    # LLM 선언 + 프롬프트 구성 + RAG 체인 구성
    rag_chain = build_chain(retriever)

    if return_retriever:
        return rag_chain, retriever, len(chunks)
    return rag_chain


# GitHub에 올린 chroma_db 불러오기 (PDF 업로드 없이 바로 사용)
@st.cache_resource(show_spinner="📚 백서 벡터 저장소를 불러오는 중...")
def load_existing():
    if not os.path.exists(CHROMA_DIR):
        return None
    embedding = OpenAIEmbeddings(model=EMB_MODEL)
    vectorstore = Chroma(collection_name=COLLECTION, embedding_function=embedding,
                         persist_directory=CHROMA_DIR)
    count = vectorstore._collection.count()
    if count == 0:
        return None
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
    return build_chain(retriever), retriever, count


# =====================================================================
# 2. 공통 LLM 도우미 함수
# =====================================================================
def retrieve(query):
    return st.session_state.retriever.invoke(query)


def retrieve_many(queries):
    """여러 질의로 검색해 중복 없이 합치기"""
    seen, docs = set(), []
    for q in queries:
        for d in retrieve(q):
            if d.page_content not in seen:
                seen.add(d.page_content)
                docs.append(d)
    return docs


def level_text():
    return f"{st.session_state.user_type} / {st.session_state.level}"


def task_system(task):
    """기능별 시스템 메시지 = 페르소나 + 기능 지시 + 공통 원칙"""
    return (f"{PERSONA[st.session_state.user_type]}\n\n[사용자 수준] {level_text()}\n\n[작업]\n{task}\n\n"
            "[공통 원칙] 제공된 [문서]에 근거하고, 문서에 없는 내용은 지어내지 않습니다. "
            "운영 규정은 기수 기준(예: 10기)을 밝히고 최신 공지·담당자 확인이 우선임을 안내합니다. "
            "근거 위치는 (p.N)으로 표기합니다.")


def llm_stream(system, user):
    llm = ChatOpenAI(model=LLM_MODEL, temperature=0.3, streaming=True)
    return (llm | StrOutputParser()).stream([("system", system), ("human", user)])


def llm_json(system, user, temperature=0.4):
    llm = ChatOpenAI(model=LLM_MODEL, temperature=temperature).bind(
        response_format={"type": "json_object"})
    content = llm.invoke([("system", system + "\n반드시 JSON 객체로만 출력합니다."),
                          ("human", user)]).content
    try:
        return json.loads(content)
    except Exception:
        m = re.search(r"\{.*\}", content, re.S)
        return json.loads(m.group()) if m else {}


def is_rule_related(text):
    return any(k in text for k in RULE_KEYWORDS)


def show_sources(docs, key):
    if not docs:
        return
    pages = sorted({page_of(d) for d in docs}, key=lambda x: (isinstance(x, str), x))
    with st.expander(f"📄 답변 근거 확인 · 백서 p.{', p.'.join(map(str, pages))}"):
        for d in docs:
            st.markdown(f"**p.{page_of(d)}**")
            st.caption(d.page_content[:350].replace("\n", " ") + " …")


def rule_badge():
    st.caption("📌 운영 규정 관련 답변입니다. 백서는 **10기 기준** 자료이므로, 다음 기수·개인 판정은 "
               "AIVLE-EDU 공지와 담당 매니저 안내가 우선합니다.")


# =====================================================================
# 3. 로드맵 PNG 출력 (기능 13)
# =====================================================================
def find_korean_font():
    from matplotlib import font_manager
    for path in font_manager.findSystemFonts():
        name = os.path.basename(path).lower()
        if any(k in name for k in ["nanumgothic", "nanumbarungothic", "notosanscjk", "notosanskr",
                                    "malgun", "applegothic"]):
            return path
    return None


def roadmap_png(rm):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    from matplotlib.patches import FancyBboxPatch

    font_path = find_korean_font()
    fp = FontProperties(fname=font_path) if font_path else FontProperties()

    W = 10
    blocks = []
    for w in rm.get("weeks", []):
        lines = []
        for it in w.get("items", []):
            text = f"• {it.get('topic', '')} — {it.get('task', '')} ({it.get('hours', '?')}h)"
            lines += textwrap.wrap(text, 60) or [""]
        blocks.append((w, lines))

    heights = [0.9 + 0.32 * len(lines) for _, lines in blocks]
    H = 1.6 + sum(h + 0.25 for h in heights) + 0.4
    fig = plt.figure(figsize=(W, H), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    fig.patch.set_facecolor("#FFFFFF")

    ax.text(0.5, H - 0.6, rm.get("title", "나의 맞춤형 학습 로드맵"), fontproperties=fp,
            fontsize=18, weight="bold", color="#1F2937", va="center")
    ax.text(0.5, H - 1.05, f"AIVLE GUIDE · {level_text()} · AI가 생성한 개인 학습 제안 (공식 일정 아님)",
            fontproperties=fp, fontsize=9, color="#6B7280", va="center")

    y = H - 1.6
    colors = ["#E60012", "#F97316", "#2563EB", "#7C3AED", "#059669", "#DB2777", "#0891B2", "#4B5563"]
    for i, ((w, lines), h) in enumerate(zip(blocks, heights)):
        c = colors[i % len(colors)]
        ax.add_patch(FancyBboxPatch((0.4, y - h), W - 0.8, h, boxstyle="round,pad=0.02,rounding_size=0.15",
                                    linewidth=1.5, edgecolor=c, facecolor="#F9FAFB"))
        ax.add_patch(FancyBboxPatch((0.4, y - 0.55), 1.3, 0.45, boxstyle="round,pad=0.02,rounding_size=0.1",
                                    linewidth=0, facecolor=c))
        ax.text(1.05, y - 0.33, f"{w.get('week', i + 1)}주차", fontproperties=fp, fontsize=11,
                color="white", ha="center", va="center", weight="bold")
        ax.text(1.9, y - 0.33, w.get("goal", ""), fontproperties=fp, fontsize=11.5,
                color="#111827", va="center", weight="bold")
        for j, line in enumerate(lines):
            ax.text(0.7, y - 0.85 - 0.32 * j, line, fontproperties=fp, fontsize=9.5,
                    color="#374151", va="center")
        y -= h + 0.25

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue(), font_path is not None


def roadmap_markdown(rm):
    md = [f"# {rm.get('title', '나의 학습 로드맵')}", "", rm.get("summary", ""), ""]
    for w in rm.get("weeks", []):
        md.append(f"## {w.get('week')}주차 · {w.get('goal', '')}")
        for it in w.get("items", []):
            md.append(f"- **{it.get('topic')}**: {it.get('task')} ({it.get('hours')}h)")
        md.append("")
    if rm.get("tips"):
        md.append("## 선배 팁")
        md += [f"- {t}" for t in rm["tips"]]
    return "\n".join(md)


# =====================================================================
# 4. 세션 상태 초기화
# =====================================================================
DEFAULTS = {
    "user_type": None, "level": None, "messages": [], "pending": None,
    "roadmap": None, "roadmap_docs": [], "done": {},
    "topic_output": None, "quiz": None, "quiz_result": None,
    "solution": None, "solution_docs": [], "inquiry": None,
    "chain": None, "retriever": None, "doc_name": None, "chunk_count": 0,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# 벡터 저장소 준비
if st.session_state.chain is None:
    try:
        loaded = load_existing()
    except Exception as e:
        loaded = None
        st.session_state.load_error = str(e)
    if loaded:
        st.session_state.chain, st.session_state.retriever, st.session_state.chunk_count = loaded
        st.session_state.doc_name = "AIVLE School 백서 (기본)"


# =====================================================================
# 5. 스타일
# =====================================================================
st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1150px;}
.hero {background: linear-gradient(120deg, #E60012 0%, #B0001A 45%, #1F2937 100%);
       color: white; padding: 28px 32px; border-radius: 18px; margin-bottom: 18px;}
.hero h1 {color: white; margin: 0 0 6px 0; font-size: 2.1rem;}
.hero p {color: #FDE8EA; margin: 0; font-size: 1.02rem;}
.card {border: 1px solid #E5E7EB; border-radius: 16px; padding: 20px; height: 100%;
       background: #FFFFFF; box-shadow: 0 2px 10px rgba(0,0,0,.04);}
.card h3 {margin-top: 0;}
.chip {display:inline-block; padding: 3px 10px; border-radius: 999px; background:#FEE2E2;
       color:#B91C1C; font-size: .8rem; margin-right: 6px; font-weight:600;}
.notice {background:#FFF7ED; border-left: 4px solid #F97316; padding: 10px 14px;
         border-radius: 8px; font-size: .9rem; color:#7C2D12;}
div[data-testid="stTabs"] button p {font-size: 1.05rem; font-weight: 600;}
</style>
""", unsafe_allow_html=True)


# =====================================================================
# 6. 시작 화면: 지원자 / 교육생 구분 (기능 4)
# =====================================================================
if st.session_state.user_type is None:
    st.markdown("""
    <div class="hero">
      <h1>🧭 AIVLE GUIDE</h1>
      <p>에이블스쿨 백서 기반 개인 맞춤형 AI 학습·생활 도우미 — 궁금한 것은 묻고, 나만의 학습 길을 찾아보세요.</p>
    </div>""", unsafe_allow_html=True)
    st.markdown("### 어떤 분이신가요?")
    st.caption("선택에 따라 추천 질문과 답변 방식이 달라집니다. 이후 사이드바에서 언제든 바꿀 수 있어요.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""<div class="card"><h3>🌱 예비 지원자</h3>
        <span class="chip">지원 자격</span><span class="chip">모집 일정</span><span class="chip">트랙 선택</span>
        <p style="margin-top:12px">에이블스쿨이 궁금하고 지원을 고민하고 있어요.</p></div>""",
                    unsafe_allow_html=True)
        if st.button("지원자로 시작하기", type="primary", width="stretch"):
            st.session_state.user_type, st.session_state.level = "지원자", LEVELS["지원자"][0]
            st.rerun()
    with c2:
        st.markdown("""<div class="card"><h3>🚀 교육생</h3>
        <span class="chip">학습 로드맵</span><span class="chip">퀴즈</span><span class="chip">문제 해결</span>
        <p style="margin-top:12px">지금 교육을 받으며 학습·출결·프로젝트 도움이 필요해요.</p></div>""",
                    unsafe_allow_html=True)
        if st.button("교육생으로 시작하기", type="primary", width="stretch"):
            st.session_state.user_type, st.session_state.level = "교육생", LEVELS["교육생"][0]
            st.rerun()
    st.stop()


# =====================================================================
# 7. 사이드바: 공통 설정 (기능 1, 4, 6)
# =====================================================================
with st.sidebar:
    st.markdown("## ⚙️ 설정")

    # 사용자 구분 (실시간 변경)
    ut = st.radio("사용자 구분", ["지원자", "교육생"], horizontal=True,
                  index=["지원자", "교육생"].index(st.session_state.user_type))
    if ut != st.session_state.user_type:
        st.session_state.user_type, st.session_state.level = ut, LEVELS[ut][0]
        st.rerun()

    # 수준 (실시간 변경)
    st.session_state.level = st.select_slider(
        "나의 단계" if ut == "지원자" else "나의 학습 수준",
        options=LEVELS[ut], value=st.session_state.level)

    st.divider()

    # 문서 업로드·교체 (기능 1)
    st.markdown("#### 📄 기준 문서")
    st.caption(f"현재: **{st.session_state.doc_name or '없음'}**"
               + (f" · {st.session_state.chunk_count}개 청크" if st.session_state.chunk_count else ""))
    uploaded = st.file_uploader("새 PDF 업로드(백서 업데이트·교체)", type=["pdf"])
    if uploaded and st.button("📥 이 문서로 RAG 다시 구성", width="stretch"):
        with st.spinner("문서를 읽고 벡터 저장소를 다시 만드는 중..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
                f.write(uploaded.getvalue())
                tmp_path = f.name
            load_existing.clear()
            chain, retriever, n = rag_pipeline(tmp_path, return_retriever=True)
            os.remove(tmp_path)
        st.session_state.update(chain=chain, retriever=retriever, chunk_count=n,
                                doc_name=uploaded.name, messages=[])
        st.success(f"반영 완료! {n}개 청크로 구성했어요.")
        st.rerun()

    st.divider()

    # 대화 관리 (기능 6)
    st.markdown("#### 💬 대화 관리")
    if st.session_state.messages:
        log = "\n\n".join(f"[{'나' if m['role'] == 'user' else 'AIVLE GUIDE'}]\n{m['content']}"
                          for m in st.session_state.messages)
        st.download_button("💾 대화 내용 저장(.txt)", log,
                           file_name=f"aivle_guide_{datetime.date.today()}.txt", width="stretch")
    if st.button("🗑️ 대화 초기화", width="stretch"):
        st.session_state.messages = []
        st.session_state.pending = None
        st.rerun()
    if st.button("🔄 처음 화면으로", width="stretch"):
        for k, v in DEFAULTS.items():
            if k not in ("chain", "retriever", "doc_name", "chunk_count"):
                st.session_state[k] = v
        st.rerun()

    st.divider()
    st.markdown('<div class="notice">📌 백서의 운영 규정은 <b>10기 기준</b>입니다. '
                '최신 공지와 담당자 안내가 항상 우선합니다.</div>', unsafe_allow_html=True)


# =====================================================================
# 8. 헤더
# =====================================================================
emoji = "🌱" if st.session_state.user_type == "지원자" else "🚀"
st.markdown(f"""
<div class="hero">
  <h1>🧭 AIVLE GUIDE</h1>
  <p>{emoji} {level_text()} 모드 · 정보를 이해하고 → 나에게 맞는 계획을 세우고 → 학습·점검하고 → 실제 문제를 해결해요.</p>
</div>""", unsafe_allow_html=True)

if st.session_state.chain is None:
    st.warning("벡터 저장소(chroma_db)를 찾지 못했어요. 왼쪽 사이드바에서 **백서 PDF를 업로드**해 주세요.")
    if st.session_state.get("load_error"):
        st.caption(f"오류: {st.session_state.load_error}")
    st.stop()

tab_chat, tab_learn, tab_solve = st.tabs(["💬 AI 상담", "📚 나의 학습", "🛠️ 문제 해결"])


# =====================================================================
# 9. 탭 1 — AI 상담 (기능 2, 3, 5, 6, 10)
# =====================================================================
with tab_chat:
    chat_area = st.container()

    with chat_area:
        # 처음 사용자: 추천 질문 (기능 3)
        if not st.session_state.messages:
            st.markdown(f"#### 👋 반가워요! {st.session_state.level} {st.session_state.user_type}에게 추천하는 질문")
            cols = st.columns(3)
            for i, q in enumerate(RECOMMENDED[(st.session_state.user_type, st.session_state.level)]):
                if cols[i].button(f"💡 {q}", key=f"rec_{i}", width="stretch"):
                    st.session_state.pending = {"q": q, "length": "기본"}
                    st.rerun()

        # 대화 기록 출력
        msgs = st.session_state.messages
        for idx, m in enumerate(msgs):
            with st.chat_message(m["role"], avatar="🙋" if m["role"] == "user" else "🧭"):
                st.markdown(m["content"])
                if m["role"] == "assistant":
                    if m.get("rule"):
                        rule_badge()          # 기수·규정 구분 (기능 10)
                    show_sources(m.get("docs", []), key=f"src_{idx}")   # 근거 페이지 (기능 2)

                    # 마지막 답변에만: 답변 조절 + 연관 질문
                    if idx == len(msgs) - 1:
                        b1, b2, _ = st.columns([1, 1, 4])
                        if b1.button("✂️ 짧게", key="shorter"):
                            st.session_state.pending = {"q": m["question"], "length": "짧게", "replace": True}
                            st.rerun()
                        if b2.button("🔍 더 자세히", key="longer"):
                            st.session_state.pending = {"q": m["question"], "length": "자세히", "replace": True}
                            st.rerun()
                        if m.get("followups"):
                            st.caption("🔗 이어서 물어보면 좋은 질문")
                            fcols = st.columns(len(m["followups"]))
                            for j, fq in enumerate(m["followups"]):
                                if fcols[j].button(fq, key=f"fu_{j}", width="stretch"):
                                    st.session_state.pending = {"q": fq, "length": "기본"}
                                    st.rerun()

    typed = st.chat_input("에이블스쿨에 대해 무엇이든 물어보세요 (예: 비전공자도 따라갈 수 있을까요?)")

    request = None
    if typed:
        request = {"q": typed, "length": "기본"}
    elif st.session_state.pending:
        request = st.session_state.pending
        st.session_state.pending = None

    if request:
        q, length = request["q"], request["length"]
        if request.get("replace") and len(st.session_state.messages) >= 2:
            st.session_state.messages = st.session_state.messages[:-2]   # 이전 답변을 새 길이로 교체

        # 최근 대화 6개를 맥락으로 전달
        history = []
        for m in st.session_state.messages[-6:]:
            history.append(HumanMessage(m["content"]) if m["role"] == "user" else AIMessage(m["content"]))

        with chat_area:
            with st.chat_message("user", avatar="🙋"):
                st.markdown(q)
            with st.chat_message("assistant", avatar="🧭"):
                docs = retrieve(q)
                answer = st.write_stream(st.session_state.chain.stream({
                    "input": q,
                    "context": format_docs_with_page(docs),
                    "history": history,
                    "persona": PERSONA[st.session_state.user_type],
                    "level": level_text(),
                    "length_guide": LENGTH[length],
                }))
                with st.spinner("연관 질문을 찾는 중..."):
                    try:
                        fu = llm_json(
                            "당신은 에이블스쿨 백서 기반 챗봇의 후속 질문 추천기입니다.",
                            f"[사용자] {level_text()}\n[질문] {q}\n[답변] {answer}\n\n"
                            f"[백서 일부]\n{format_docs(docs)[:1500]}\n\n"
                            "사용자가 이어서 궁금해할 만하고 백서로 답할 수 있는 짧은 질문 3개를 "
                            '{"questions": ["...", "...", "..."]} 형식으로 만드세요. 각 질문은 30자 이내.')
                        followups = fu.get("questions", [])[:3]
                    except Exception:
                        followups = []

        st.session_state.messages.append({"role": "user", "content": q})
        st.session_state.messages.append({
            "role": "assistant", "content": answer, "question": q, "docs": docs,
            "followups": followups, "rule": is_rule_related(q + answer),
        })
        st.rerun()


# =====================================================================
# 10. 탭 2 — 나의 학습 (기능 7, 8, 12, 13)
# =====================================================================
with tab_learn:
    st.markdown("### 🗺️ 개인 맞춤형 학습 로드맵")
    st.caption("백서의 학습 전략·교육과정·선배 경험을 바탕으로 AI가 나만의 계획을 제안합니다. "
               "**AI가 만든 개인 학습 제안이며 공식 교육 일정이 아닙니다.**")

    with st.form("roadmap_form"):
        c1, c2 = st.columns(2)
        goal = c1.text_input("학습 목표", value="RAG 챗봇을 직접 구현하고 성능을 검증할 수 있게 되기")
        interests = c2.multiselect("관심 분야", INTERESTS, default=["RAG·LLM", "프로젝트·협업"])
        c3, c4 = st.columns(2)
        weeks = c3.slider("기간(주)", 1, 8, 4)
        hours = c4.slider("하루 학습 가능 시간(수업 외)", 1, 6, 2)
        background = st.text_input("나의 배경 (선택)", placeholder="예: 비전공자, 파이썬 기초만 앎")
        submitted = st.form_submit_button("✨ 로드맵 만들기", type="primary", width="stretch")

    if submitted:
        with st.spinner("백서를 참고해 나만의 로드맵을 설계하는 중..."):
            docs = retrieve_many([f"{st.session_state.level} 학습 전략 복습 방법",
                                  f"{goal} {' '.join(interests)}",
                                  "학습 계획 예시 주차별", "선배 후기 조언 프로젝트"])
            rm = llm_json(
                task_system("사용자의 수준·목표·기간·가용 시간에 맞는 주차별 학습 로드맵을 설계합니다. "
                            "수준별 차이: 초급은 개념 이해와 제공 코드 실행, 중급은 코드 수정·설정 비교, "
                            "고급은 품질 평가·최적화·배포 검증 중심으로 구성합니다."),
                f"[목표] {goal}\n[관심 분야] {', '.join(interests)}\n[기간] {weeks}주\n"
                f"[하루 가용 시간] {hours}시간\n[배경] {background or '미입력'}\n\n"
                f"[문서]\n{format_docs_with_page(docs)}\n\n"
                '다음 JSON 형식으로 작성: {"title": "로드맵 제목", "summary": "2~3문장 요약", '
                '"weeks": [{"week": 1, "goal": "주차 목표", "items": [{"topic": "학습 항목(15자 이내)", '
                '"task": "구체적 활동", "hours": 4}]}], "tips": ["백서 근거 선배 팁 (p.N)"]} '
                f"weeks는 정확히 {weeks}개, 주차별 items 3~4개.")
        st.session_state.update(roadmap=rm, roadmap_docs=docs, done={}, topic_output=None)

    rm = st.session_state.roadmap
    if rm and rm.get("weeks"):
        st.markdown(f"#### {rm.get('title', '나의 학습 로드맵')}")
        st.info(rm.get("summary", ""))

        all_items = [(w.get("week"), it) for w in rm["weeks"] for it in w.get("items", [])]
        done_cnt = sum(1 for k, v in st.session_state.done.items() if v)
        st.progress(done_cnt / max(len(all_items), 1), text=f"진행률 {done_cnt}/{len(all_items)}")

        wcols = st.columns(min(len(rm["weeks"]), 4))
        for i, w in enumerate(rm["weeks"]):
            with wcols[i % len(wcols)]:
                with st.container(border=True):
                    st.markdown(f"**{w.get('week')}주차**  \n{w.get('goal', '')}")
                    for j, it in enumerate(w.get("items", [])):
                        key = f"done_{i}_{j}"
                        st.session_state.done[key] = st.checkbox(
                            f"{it.get('topic')} ({it.get('hours')}h)", key=key,
                            value=st.session_state.done.get(key, False), help=it.get("task"))

        if rm.get("tips"):
            with st.expander("💬 백서 속 선배 팁"):
                for t in rm["tips"]:
                    st.markdown(f"- {t}")

        # 로드맵 내보내기 (기능 13)
        d1, d2 = st.columns(2)
        try:
            png, has_font = roadmap_png(rm)
            d1.download_button("🖼️ 로드맵 PNG 저장", png, file_name="my_aivle_roadmap.png",
                               mime="image/png", width="stretch")
            if not has_font:
                d1.caption("⚠️ 한글 폰트가 없어 글자가 깨질 수 있어요. 저장소에 packages.txt(fonts-nanum)를 추가하세요.")
        except Exception as e:
            d1.caption(f"PNG 생성 실패: {e}")
        d2.download_button("📝 로드맵 Markdown 저장", roadmap_markdown(rm),
                           file_name="my_aivle_roadmap.md", width="stretch")

        # 학습 항목 선택 → 설명 / 퀴즈 / 실무 활용 (기능 7 → 8, 12)
        st.markdown("---")
        st.markdown("### 🎯 학습 항목 선택")
        labels = [f"{wk}주차 · {it.get('topic')}" for wk, it in all_items]
        sel = st.selectbox("공부할 항목을 고르세요", range(len(labels)), format_func=lambda i: labels[i])
        topic = all_items[sel][1].get("topic", "")

        a1, a2, a3 = st.columns(3)
        action = None
        if a1.button("📖 관련 설명 보기", width="stretch"):
            action = "explain"
        if a2.button("📝 복습 퀴즈 풀기", width="stretch"):
            action = "quiz"
        if a3.button("💼 실무 활용 탐색", width="stretch"):
            action = "practice"

        if action in ("explain", "practice"):
            docs = retrieve(topic)
            if action == "explain":
                task = (f"'{topic}'을(를) 사용자 수준에 맞게 설명합니다. 구성: ① 한 줄 정의 ② 쉬운 비유 "
                        "③ 핵심 포인트 3가지 ④ 바로 해볼 실습 한 가지.")
            else:
                task = (f"'{topic}'을(를) KT·기업 DX 현장과 AI 개발자/DX 컨설턴트 직무, 미니·빅프로젝트에서 "
                        "어떻게 활용할 수 있는지 탐색합니다. 구성: ① 활용 장면 2~3개 ② 프로젝트 아이디어 1개 "
                        "③ 포트폴리오에 쓸 수 있는 한 문장. 백서 근거와 일반 지식을 구분해 표시하세요.")
            with st.container(border=True):
                out = st.write_stream(llm_stream(task_system(task),
                                                 f"[학습 항목] {topic}\n\n[문서]\n{format_docs_with_page(docs)}"))
            st.session_state.topic_output = {"title": topic, "text": out, "docs": docs}
        elif st.session_state.topic_output:
            with st.container(border=True):
                st.markdown(f"**{st.session_state.topic_output['title']}**")
                st.markdown(st.session_state.topic_output["text"])
        if st.session_state.topic_output:
            show_sources(st.session_state.topic_output["docs"], key="topic_src")
    else:
        topic, action = None, None

    # AI 퀴즈·복습 (기능 8)
    st.markdown("---")
    st.markdown("### 📝 AI 퀴즈 · 실력 점검")
    q1, q2, q3 = st.columns([3, 1, 1])
    quiz_topic = q1.text_input("퀴즈 주제", value=topic or "RAG 개념과 구현",
                               key=f"quiz_topic_{topic}")
    diff = q2.selectbox("난이도", ["초급", "중급", "고급"],
                        index=["초급", "중급", "고급"].index(st.session_state.level)
                        if st.session_state.level in ["초급", "중급", "고급"] else 0)
    n_q = q3.selectbox("문항 수", [3, 5], index=0)

    if q1.button("🎲 퀴즈 만들기", type="primary") or action == "quiz":
        with st.spinner("백서를 바탕으로 문제를 출제하는 중..."):
            docs = retrieve_many([quiz_topic, f"{quiz_topic} 개념 정리"])
            quiz = llm_json(
                task_system(f"'{quiz_topic}'에 대해 {diff} 난이도의 4지선다 복습 퀴즈를 출제합니다. "
                            "초급은 개념 확인, 중급은 적용·비교, 고급은 원인 분석·평가 문제로 냅니다. "
                            "반드시 [문서] 내용으로 정답을 확정할 수 있는 문제만 냅니다."),
                f"[문서]\n{format_docs_with_page(docs)}\n\n"
                f'{n_q}문항을 {{"questions": [{{"q": "문제", "options": ["보기1","보기2","보기3","보기4"], '
                '"answer": 0, "explanation": "해설 (p.N)"}]}} 형식으로. answer는 정답 보기의 인덱스(0~3).',
                temperature=0.6)
        st.session_state.quiz = {"topic": quiz_topic, "diff": diff, "items": quiz.get("questions", []),
                                 "id": datetime.datetime.now().strftime("%H%M%S%f")}
        st.session_state.quiz_result = None

    quiz = st.session_state.quiz
    if quiz and quiz["items"]:
        with st.form("quiz_form"):
            st.markdown(f"**주제: {quiz['topic']} · 난이도: {quiz['diff']}**")
            picks = []
            for i, item in enumerate(quiz["items"]):
                picks.append(st.radio(f"Q{i + 1}. {item['q']}", range(len(item["options"])),
                                      format_func=lambda k, it=item: it["options"][k],
                                      index=None, key=f"quiz_{i}_{quiz['id']}"))
            graded = st.form_submit_button("✅ 채점하기", type="primary")
        if graded:
            st.session_state.quiz_result = picks

        if st.session_state.quiz_result is not None:
            picks = st.session_state.quiz_result
            score = sum(1 for p, it in zip(picks, quiz["items"]) if p == it.get("answer"))
            total = len(quiz["items"])
            rate = score / total
            st.metric("점수", f"{score} / {total}", f"{rate:.0%}")
            if rate >= 0.8:
                st.success(f"🎉 {quiz['diff']} 수준을 잘 이해하고 있어요! 다음 난이도에 도전해 보세요.")
            elif rate >= 0.5:
                st.warning("👍 기본은 잡혔어요. 틀린 문제의 해설과 근거 페이지를 복습한 뒤 다시 풀어 보세요.")
            else:
                st.error("💪 한 단계 낮은 난이도로 개념부터 다시 다져 보세요. 꾸준함이 실력이 됩니다!")
            for i, (p, it) in enumerate(zip(picks, quiz["items"])):
                ok = p == it.get("answer")
                with st.expander(f"{'⭕' if ok else '❌'} Q{i + 1}. {it['q']}", expanded=not ok):
                    st.markdown(f"- 내 답: {it['options'][p] if p is not None else '미응답'}")
                    st.markdown(f"- 정답: **{it['options'][it.get('answer', 0)]}**")
                    st.markdown(f"- 해설: {it.get('explanation', '')}")


# =====================================================================
# 11. 탭 3 — 문제 해결 (기능 9, 10, 11)
# =====================================================================
with tab_solve:
    st.markdown("### 🛠️ 상황별 문제 해결")
    st.caption("출결·공가·실습 오류·프로젝트 등 지금 겪는 상황을 알려주세요. 백서 기준으로 할 일을 정리해 드려요.")

    category = st.pills("상황 유형", SITUATIONS, default=SITUATIONS[0]) or "기타"
    situation = st.text_area("상황 설명", height=110,
                             placeholder="예: 병원 진료 때문에 오전에 늦을 것 같아요. 어떻게 처리해야 하나요?")
    if category == "실습·코드 오류":
        err = st.text_area("오류 메시지 (선택)", height=90, placeholder="Traceback ... 을 붙여넣으세요")
    else:
        err = ""

    if st.button("🔎 해결 방법 안내받기", type="primary", disabled=not situation.strip()):
        docs = retrieve_many([f"{category} {situation}", category])
        task = ("사용자의 상황에 대해 다음 형식으로 안내합니다.\n"
                "### 1. 상황 요약\n### 2. 백서 기준 (기수 표기, 공식 운영 기준/실천 제안 구분)\n"
                "### 3. 지금 해야 할 일 (번호 목록, 기한·증빙 포함)\n"
                "### 4. 담당자 확인 필요 여부 — '필요' 또는 '불필요'와 그 이유\n"
                "코드 오류라면 원인 후보와 확인 순서를 제시합니다.")
        with st.container(border=True):
            sol = st.write_stream(llm_stream(
                task_system(task),
                f"[상황 유형] {category}\n[상황] {situation}\n[오류 메시지] {err or '없음'}\n\n"
                f"[문서]\n{format_docs_with_page(docs)}"))
        st.session_state.update(solution={"category": category, "situation": situation, "text": sol},
                                solution_docs=docs, inquiry=None)
    elif st.session_state.solution:
        with st.container(border=True):
            st.markdown(st.session_state.solution["text"])

    if st.session_state.solution:
        show_sources(st.session_state.solution_docs, key="solve_src")
        if is_rule_related(st.session_state.solution["text"]):
            rule_badge()

        # 공식 문의문 자동 작성 (기능 11)
        st.markdown("#### ✉️ 담당자 확인이 필요하다면")
        if st.button("공식 문의문 자동 작성"):
            s = st.session_state.solution
            with st.spinner("문의문을 작성하는 중..."):
                text = "".join(llm_stream(
                    task_system("담당 매니저에게 보낼 공손하고 간결한 공식 문의문을 작성합니다. "
                                "구성: 제목 / 인사 / 소속([기수]·[반]·[이름]) / 상황(날짜·시간 포함) / "
                                "문의 사항(번호 목록) / 첨부 예정 증빙 / 마무리 인사. "
                                "개인정보는 [ ] 빈칸으로 두고, 비밀번호·인증번호는 절대 넣지 않습니다."),
                    f"[상황 유형] {s['category']}\n[상황] {s['situation']}\n[안내 내용]\n{s['text']}"))
            st.session_state.inquiry = text
        if st.session_state.inquiry:
            edited = st.text_area("문의문 (수정 후 복사해 사용하세요)", st.session_state.inquiry, height=300)
            st.download_button("💾 문의문 저장(.txt)", edited, file_name="aivle_inquiry.txt")
