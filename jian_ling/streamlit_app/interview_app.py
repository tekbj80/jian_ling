import json
import os

import streamlit as st
from openai import OpenAI

from jian_ling import Session
from jian_ling.chat_session import get_response
from jian_ling.interview import (
    analyze_cv_against_job_description,
    cv_job_analysis_accepted,
    parse_analysis_output,
)
from jian_ling.interview.helpers import run_interviewer_opening_turn
from jian_ling.prompts.personas import interview_personas as persona_defs
from jian_ling.prompts.tasks import interview_tasks as task_defs
from jian_ling.prompts.interview_prompt import (
    build_interviewer_prompt,
    build_session_summary_prompt,
)

OPENAI_ALLOWED_MODELS = [
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4o",
    "gpt-4o-mini",
]
OPENAI_DEFAULT_MODEL = "gpt-4.1"

# Input limits (misuse prevention / cost control)
MAX_JOB_DESCRIPTION_CHARS = 8000
MAX_CHAT_MESSAGE_CHARS = 8000

PERSONA_OPTIONS = {
    "Friendly HR Consultant": persona_defs.FRIENDLY_HR_PERSON.strip(),
    "Qin Shi Huang": persona_defs.QIN_SHI_HUANG_PERSONA,
}

TASK_OPTIONS = task_defs.INTERVIEW_TASK_DICT
if not TASK_OPTIONS:
    raise ValueError("INTERVIEW_TASK_DICT is empty. Add at least one interview task.")


def _format_analysis_field(value):
    """Render gaps/suitability whether the model returned a string or a list."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        lines = [str(x).strip() for x in value if str(x).strip()]
        return "\n".join(f"{i + 1}. {line}" for i, line in enumerate(lines))
    return str(value).strip()


def _suitability_context_for_prompt(value):
    """Serialize analysis for embedding in a system prompt."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value).strip()


def _format_transcript_for_summary(messages):
    """Turn display_messages into markdown for the summarizer."""
    if not messages:
        return ""
    blocks = []
    for m in messages:
        role = m.get("role", "")
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            label = "Candidate"
        elif role == "assistant":
            label = "Interviewer"
        else:
            label = role
        blocks.append(f"### {label}\n{content}")
    return "\n\n".join(blocks)


def _run_session_summary(client, model, temperature, top_p):
    """Send full display transcript to summarizer; sets interview_session_summary or st.error."""
    transcript = _format_transcript_for_summary(
        st.session_state.interview_session.display_messages
    )
    if not transcript.strip():
        st.warning("There is no interview dialogue to summarize yet.")
        return

    summary_sys = build_session_summary_prompt(
        (st.session_state.job_description or "").strip(),
        _suitability_context_for_prompt(st.session_state.suitability_gap_text),
    )
    user_payload = (
        "Here is the full interview transcript.\n\n"
        f"{transcript}\n\n"
        "Produce the summary, feedback, and improvement suggestions as specified "
        "in your instructions."
    )
    try:
        with st.spinner("Summarizing your answers..."):
            raw = get_response(
                [{"role": "user", "content": user_payload}],
                client,
                server_prompt=summary_sys,
                model=model,
                stream=False,
                temperature=temperature,
                top_p=top_p,
            )
        try:
            payload = Session._parse_json_payload(raw)
            st.session_state.interview_session_summary = payload["response"]
        except Exception:
            text = (raw or "").strip()
            st.session_state.interview_session_summary = (
                text or "The model returned a response that could not be parsed as JSON."
            )
        st.success("Summary is ready — see Session summary below the chat.")
    except Exception as exc:
        st.error(f"Could not generate summary: {exc}")


# Sidebar-only: style the session-summary primary button red (no primary buttons elsewhere in sidebar).
_SIDEBAR_RED_PRIMARY_BUTTON_CSS = """
<style>
    div[data-testid="stSidebar"] button[kind="primary"],
    div[data-testid="stSidebar"] [data-testid="baseButton-primary"] {
        background-color: #c62828 !important;
        border: 1px solid #b71c1c !important;
        color: #ffffff !important;
    }
    div[data-testid="stSidebar"] button[kind="primary"]:hover,
    div[data-testid="stSidebar"] [data-testid="baseButton-primary"]:hover {
        background-color: #b71c1c !important;
        border-color: #7f0000 !important;
        color: #ffffff !important;
    }
</style>
"""


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
        "interview_session_summary": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


st.set_page_config(page_title="jian_ling Interview App", page_icon=":briefcase:")
st.title("jian_ling Interview App")
st.caption(
    "Upload your CV PDF and job description below, generate analysis, then answer the interviewer's questions."
)

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

with st.sidebar.expander("Generation settings", expanded=False):
    st.caption("OpenAI sampling parameters for interview chat (and opening question).")
    temperature = st.slider("Temperature", min_value=0.0, max_value=2.0, value=0.7, step=0.05)
    top_p = st.slider("Top-p", min_value=0.01, max_value=1.0, value=1.0, step=0.01)

if st.session_state.analysis_ready:
    st.sidebar.caption("Wrap-up: summarize everything you said so far (full transcript).")
    st.sidebar.markdown(_SIDEBAR_RED_PRIMARY_BUTTON_CSS, unsafe_allow_html=True)
    if st.sidebar.button(
        "Stop and summarize",
        type="primary",
        use_container_width=True,
        help="Send the full chat transcript to the model for a written summary and coaching.",
        key="stop_summarize_sidebar",
    ):
        _run_session_summary(client, model, temperature, top_p)

st.sidebar.markdown("---")

st.subheader("CV and job posting")
cv_file = st.file_uploader("CV (PDF)", type=["pdf"], accept_multiple_files=False)
st.text_area(
    "Job description",
    height=220,
    key="job_description",
    help=f"Maximum {MAX_JOB_DESCRIPTION_CHARS} characters.",
    max_chars=MAX_JOB_DESCRIPTION_CHARS,
)
_jd = st.session_state.get("job_description") or ""
st.caption(f"Job description: {len(_jd)} / {MAX_JOB_DESCRIPTION_CHARS} characters")

if st.button("Generate suitability / gap analysis", type="primary"):
    job_description_input = (st.session_state.get("job_description") or "").strip()
    if provider != "OpenAI":
        st.error("Suitability-gap analysis requires OpenAI due to the file upload API.")
        st.stop()
    if cv_file is None:
        st.error("Please select a PDF CV file.")
        st.stop()
    if (cv_file.type or "").lower() not in {"application/pdf"} and not cv_file.name.lower().endswith(".pdf"):
        st.error("Selected file must be a PDF.")
        st.stop()
    if not job_description_input:
        st.error("Please provide a job description.")
        st.stop()

    # Keep st.stop() / errors outside st.spinner so the spinner context always exits cleanly
    # (st.stop() inside the spinner can leave the UI stuck showing the spinner).
    with st.spinner("Uploading CV and generating suitability-gap analysis..."):
        cv_upload = client.files.create(file=cv_file, purpose="user_data")
        st.session_state.cv_file_id = cv_upload.id
        st.session_state.cv_file_name = getattr(cv_upload, "filename", cv_file.name)

        response = analyze_cv_against_job_description(
            client=client,
            cv_file_id=st.session_state.cv_file_id,
            job_description=job_description_input,
            model=model,
        )

    parsed = parse_analysis_output(response)
    ok, rejection_message = cv_job_analysis_accepted(parsed)
    if not ok:
        st.session_state.analysis_ready = False
        st.session_state.suitability_gap_text = parsed
        st.error(rejection_message)
        st.error("Invalid CV or job description — fix your inputs and click Generate again.")
        st.stop()

    st.session_state.suitability_gap_text = parsed
    st.session_state.analysis_ready = True
    st.session_state.interview_session_summary = ""
    st.session_state.interview_session = Session(client=client, model=model)

    opening_prompt = build_interviewer_prompt(
        job_description_input,
        st.session_state.suitability_gap_text,
        TASK_OPTIONS[selected_task_name],
        PERSONA_OPTIONS[selected_persona_name],
    )
    st.session_state.server_prompt_text = opening_prompt["content"]
    active_server_prompt = {"role": "system", "content": st.session_state.server_prompt_text}
    with st.spinner("Interviewer is asking the first question..."):
        run_interviewer_opening_turn(
            st.session_state.interview_session,
            active_server_prompt,
            model=model,
            stream=False,
            temperature=temperature,
            top_p=top_p,
        )

if st.session_state.analysis_ready:
    with st.sidebar.expander("Uploaded CV File", expanded=False):
        st.write(st.session_state.cv_file_name)
        st.code(st.session_state.cv_file_id)

    with st.expander("Suitability/Gap Analysis", expanded=True):
        analysis = st.session_state.suitability_gap_text
        if isinstance(analysis, dict):
            if analysis.get("inputs_valid") is False:
                st.warning(
                    analysis.get("rejection_reason")
                    or "These inputs were not accepted as a CV and job description."
                )
            gaps = analysis.get("gaps", "")
            suitability = analysis.get("suitability", "")

            st.markdown("## Gaps")
            st.markdown(_format_analysis_field(gaps) or "_No gaps returned._")

            st.markdown("## Suitability")
            st.markdown(_format_analysis_field(suitability) or "_No suitability points returned._")
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

    if st.session_state.get("interview_session_summary"):
        with st.expander("Session summary", expanded=True):
            st.markdown(st.session_state.interview_session_summary)

    st.caption(
        "Use the red **Stop and summarize** button in the sidebar (under Generation settings) "
        "for a full written summary of your answers."
    )
    st.caption(
        f"Each chat message: max {MAX_CHAT_MESSAGE_CHARS} characters "
        f"(input stops accepting more once you reach the limit)."
    )
    prompt = st.chat_input(
        "Your answer or follow-up...",
        max_chars=MAX_CHAT_MESSAGE_CHARS,
    )
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
                temperature=temperature,
                top_p=top_p,
            ):
                streamed_content += chunk
                assistant_placeholder.markdown(streamed_content)
            assistant_placeholder.markdown(st.session_state.interview_session.current_message)
else:
    st.info("When you are ready, use **Generate suitability / gap analysis** above to start.")
