
import json
import base64
import streamlit as st
from openai import OpenAI
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# OpenAI 클라이언트 생성
client = OpenAI()

# Google 연락처 권한
SCOPES = ["https://www.googleapis.com/auth/contacts"]

# 페이지 설정
st.set_page_config(page_title="AI 비서 에이블", page_icon="🤖")
st.title("🤖 AI 비서 에이블")
st.caption("명함을 올리고 음성으로 연락처 저장을 요청해 주세요.")

# 역할 지정
sys_role = """
당신은 '김 대리'의 개인 비서 '에이블'입니다.
김 대리가 명함 이미지의 연락처 저장을 요청하면 save_contact 도구를 사용합니다.
명함에 적힌 정보만 사용하고, 명함에 없는 항목은 빈 문자열로 입력하십시오.
저장 요청이 아니면 도구를 사용하지 말고 답변하십시오.
답변은 한국어로 작성하고, 없는 내용은 지어내지 마십시오.
"""

# 도구 정의
tools = [{
    "type": "function",
    "name": "save_contact",
    "description": "명함에서 읽은 정보를 Google 연락처에 저장합니다.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "이름"},
            "phone": {"type": "string", "description": "전화번호. 없으면 빈 문자열"},
            "email": {"type": "string", "description": "이메일. 없으면 빈 문자열"},
            "company": {"type": "string", "description": "회사명. 없으면 빈 문자열"},
            "title": {"type": "string", "description": "직책. 없으면 빈 문자열"}
        },
        "required": ["name", "phone", "email", "company", "title"],
        "additionalProperties": False
    },
    "strict": True
}]

# Google 연락처 저장 함수
def save_contact(name, phone, email, company, title):
    try:
        creds = Credentials.from_authorized_user_info(
           json.loads(st.secrets["GOOGLE_TOKEN"]),
           SCOPES
        )
        service = build("people", "v1", credentials=creds)

        contact = {"names": [{"givenName": name}]}
        if phone:
            contact["phoneNumbers"] = [{"value": phone}]
        if email:
            contact["emailAddresses"] = [{"value": email}]
        if company or title:
            contact["organizations"] = [{"name": company, "title": title}]

        service.people().createContact(body=contact).execute()
        return {"status": "success"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}

# 입력 영역
with st.form("contact_form", clear_on_submit=True):
    card_image = st.file_uploader("명함 이미지 업로드", type=["png", "jpg", "jpeg"])
    audio_value = st.audio_input("예: 이 명함을 연락처에 저장해 줘")
    submit = st.form_submit_button("요청하기", use_container_width=True)

# 버튼을 눌렀을 때만 실행
if submit:
    # 입력 확인
    if card_image is None or audio_value is None:
        st.warning("명함 이미지와 음성 요청을 모두 입력해 주세요.")
        st.stop()

    with st.spinner("에이블이 처리하고 있습니다..."):
        # STT: 음성 → 텍스트
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.wav", audio_value, "audio/wav")
        )

        # 명함 이미지를 base64 문자열로 변환
        encoded_image = base64.b64encode(card_image.getvalue()).decode("utf-8")

        # 1단계: 음성 요청 + 명함 이미지 + 도구 정의 전달
        response = client.responses.create(
            model="gpt-4o-mini",
            input=[
                {"role": "system", "content": sys_role},
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": transcript.text},
                        {
                            "type": "input_image",
                            "image_url": f"data:{card_image.type};base64,{encoded_image}"
                        }
                    ]
                }
            ],
            tools=tools,
            tool_choice="auto"
        )

        # 도구 필요 여부 확인
        tool_calls = [
            item for item in response.output
            if item.type == "function_call"
        ]

        saved_contacts = []

        if not tool_calls:
            # 도구가 필요 없으면 답변 사용
            answer = response.output_text
        else:
            # 2단계: 모델이 요청한 tool 실행
            tool_outputs = []
            for item in tool_calls:
                args = json.loads(item.arguments)

                if item.name == "save_contact":
                    result = save_contact(**args)
                    saved_contacts.append((args, result))

                    tool_outputs.append({
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": json.dumps(result, ensure_ascii=False)
                    })

            # 3단계: tool 결과를 모델에 다시 전달
            final_response = client.responses.create(
                model="gpt-4o-mini",
                previous_response_id=response.id,
                input=tool_outputs
            )
            answer = final_response.output_text

    # 결과 출력
    st.subheader("요청 내용")
    st.write(transcript.text)

    st.subheader("명함 이미지")
    st.image(card_image.getvalue(), width=400)

    st.subheader("에이블의 답변")
    st.write(answer)

    # 실제 저장 결과 출력
    for args, result in saved_contacts:
        if result["status"] == "success":
            st.success("Google 연락처에 저장했습니다.")
            st.link_button("구글 연락처로 이동", "https://contacts.google.com")
        else:
            st.error(f"연락처 저장 실패: {result['error']}")
