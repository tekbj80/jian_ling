import json
import os

import streamlit as st
from openai import OpenAI

from jian_ling import Session
from jian_ling.interview import analyze_cv_against_job_description, parse_analysis_output
from jian_ling.prompts.personas import interview_personas as persona_defs
from jian_ling.prompts.tasks import interview_tasks as task_defs
from jian_ling.prompts.interview_prompt import build_interviewer_prompt

OPENAI_ALLOWED_MODELS = [
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4o",
    "gpt-4o-mini",
]
OPENAI_DEFAULT_MODEL = "gpt-4.1"

PERSONA_OPTIONS = {
    "Friendly HR Consultant": persona_defs.FRIENDLY_HR_PERSON.strip(),
    "Qin Shi Huang": persona_defs.QIN_SHI_HUANG_PERSONA,
}

TASK_OPTIONS = task_defs.INTERVIEW_TASK_DICT
if not TASK_OPTIONS:
    raise ValueError("INTERVIEW_TASK_DICT is empty. Add at least one interview task.")

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

initial_default_model = (
    OPENAI_DEFAULT_MODEL if provider == "OpenAI" and OPENAI_DEFAULT_MODEL in available_models else available_models[0]
)
initialize_state(client=client, default_model=initial_default_model)

if provider == "OpenAI":
    allowed_available_models = [m for m in OPENAI_ALLOWED_MODELS if m in available_models]
    if not allowed_available_models:
        st.error(
            "None of the required OpenAI models are available for this API key/account. "
            "Expected one of: gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, gpt-4o, gpt-4o-mini."
        )
        st.stop()
    model_options = allowed_available_models
else:
    model_options = available_models

session_model = st.session_state.interview_session.model
if provider == "OpenAI" and session_model not in model_options:
    st.session_state.interview_session.model = OPENAI_DEFAULT_MODEL if OPENAI_DEFAULT_MODEL in model_options else model_options[0]
elif provider != "OpenAI" and session_model not in model_options:
    st.session_state.interview_session.model = model_options[0]

default_model = st.session_state.interview_session.model
default_index = model_options.index(default_model) if default_model in model_options else 0
model = st.sidebar.selectbox("Model", options=model_options, index=default_index)
st.session_state.interview_session.model = model
selected_persona_name = st.sidebar.selectbox("Persona", options=list(PERSONA_OPTIONS.keys()), index=0)
selected_task_name = st.sidebar.selectbox("Task", options=list(TASK_OPTIONS.keys()), index=0)

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
            model=model,
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
        st.session_state.job_description,
        st.session_state.suitability_gap_text,
        TASK_OPTIONS[selected_task_name],
        PERSONA_OPTIONS[selected_persona_name],
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
