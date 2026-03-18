import json
import os

import streamlit as st
from openai import OpenAI

from jian_ling import Session
from jian_ling.prompts.interview_prompt import JOB_CV_ANALYST_PROMPT, build_interviewer_prompt

def build_client(provider):
    if provider == "OpenAI":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            st.error("Missing OPENAI_API_KEY. Set it in your environment and restart Streamlit.")
            st.stop()
        return OpenAI(api_key=api_key)

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        st.error("Missing DEEPSEEK_API_KEY. Set it in your environment and restart Streamlit.")
        st.stop()
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def list_model_ids(client):
    response = client.models.list()
    models = getattr(response, "data", response)
    return sorted({model.id for model in models if hasattr(model, "id")})


def parse_analysis_output(response):
    raw_text = getattr(response, "output_text", "") or ""
    raw_text = raw_text.strip()
    if not raw_text:
        return "No analysis returned."

    try:
        payload = json.loads(raw_text)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass

    return raw_text


def analyze_cv_against_job_description(client, cv_file_id, job_description, model="gpt-5-mini"):
    return client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_file", "file_id": cv_file_id},
                    {"type": "input_text", "text": f"This is the job description: {job_description}"},
                ],
            },
            JOB_CV_ANALYST_PROMPT,
        ],
    )


def initialize_state(client, default_model):
    if "interview_session" not in st.session_state:
        st.session_state.interview_session = Session(client=client, model=default_model)
    else:
        st.session_state.interview_session.client = client

    defaults = {
        "cv_file_id": "",
        "cv_file_name": "",
        "job_description": "",
        "suitability_gap_text": "",
        "analysis_ready": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


st.set_page_config(page_title="jian_ling Interview App", page_icon=":briefcase:")
st.title("jian_ling Interview App")
st.caption("Upload CV PDF and job description, then start interview chat.")

provider = st.sidebar.selectbox("LLM Provider", options=["OpenAI", "DeepSeek"])
client = build_client(provider=provider)

try:
    available_models = list_model_ids(client=client)
except Exception as exc:
    st.error(f"Could not load model list from {provider}: {exc}")
    st.stop()

if not available_models:
    st.error(f"No models returned from {provider}.")
    st.stop()

initialize_state(client=client, default_model=available_models[0])

default_model = st.session_state.interview_session.model
default_index = available_models.index(default_model) if default_model in available_models else 0
model = st.sidebar.selectbox("Model", options=available_models, index=default_index)
st.session_state.interview_session.model = model

st.sidebar.markdown("---")
cv_file = st.sidebar.file_uploader("CV PDF", type=["pdf"], accept_multiple_files=False)
job_description_input = st.sidebar.text_area(
    "Job Description",
    value=st.session_state.job_description,
    height=220,
)

if st.sidebar.button("Generate Suitability Gap", type="primary"):
    if provider != "OpenAI":
        st.sidebar.error("Suitability-gap analysis requires OpenAI due to file upload API.")
        st.stop()
    if cv_file is None:
        st.sidebar.error("Please select a PDF CV file.")
        st.stop()
    if (cv_file.type or "").lower() not in {"application/pdf"} and not cv_file.name.lower().endswith(".pdf"):
        st.sidebar.error("Selected file must be a PDF.")
        st.stop()
    if not job_description_input.strip():
        st.sidebar.error("Please provide a job description.")
        st.stop()

    with st.spinner("Uploading CV and generating suitability-gap analysis..."):
        cv_upload = client.files.create(file=cv_file, purpose="user_data")
        st.session_state.cv_file_id = cv_upload.id
        st.session_state.cv_file_name = getattr(cv_upload, "filename", cv_file.name)
        st.session_state.job_description = job_description_input.strip()

        response = analyze_cv_against_job_description(
            client=client,
            cv_file_id=st.session_state.cv_file_id,
            job_description=st.session_state.job_description,
        )
        st.session_state.suitability_gap_text = parse_analysis_output(response)
        st.session_state.analysis_ready = True
        st.session_state.interview_session = Session(client=client, model=model)

if st.session_state.analysis_ready:
    with st.sidebar.expander("Uploaded CV File", expanded=False):
        st.write(st.session_state.cv_file_name)
        st.code(st.session_state.cv_file_id)

    with st.expander("Suitability/Gap Analysis", expanded=True):
        analysis = st.session_state.suitability_gap_text
        if isinstance(analysis, dict):
            gaps = str(analysis.get("gaps", "")).strip()
            suitability = str(analysis.get("suitability", "")).strip()

            st.markdown("## Gaps")
            st.markdown(gaps or "_No gaps returned._")

            st.markdown("## Suitability")
            st.markdown(suitability or "_No suitability points returned._")
        else:
            st.markdown(str(analysis))
    interviewer_prompt = build_interviewer_prompt(
        job_description=st.session_state.job_description,
        job_suitability_analysis=st.session_state.suitability_gap_text,
    )
    st.session_state.server_prompt_text = interviewer_prompt["content"]

    with st.sidebar.expander("Server Prompt", expanded=True):
        st.text_area("System prompt", key="server_prompt_text", height=260)

    with st.sidebar.expander("Session.messages", expanded=False):
        st.caption("Read-only compact session context sent to the LLM.")
        st.code(
            json.dumps(st.session_state.interview_session.messages, indent=2, ensure_ascii=False),
            language="json",
        )

    for message in st.session_state.interview_session.display_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Let's do this! Ask me anything...")
    if prompt:
        active_server_prompt = {"role": "system", "content": st.session_state.server_prompt_text}

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            assistant_placeholder = st.empty()
            streamed_content = ""
            for chunk in st.session_state.interview_session.chat(
                message=prompt,
                model=model,
                server_prompt=active_server_prompt,
                stream=True,
            ):
                streamed_content += chunk
                assistant_placeholder.markdown(streamed_content)
            assistant_placeholder.markdown(st.session_state.interview_session.current_message)
else:
    st.info("Use the sidebar to upload a PDF and generate suitability/gap first.")
