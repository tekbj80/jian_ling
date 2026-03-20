import json
from typing import Any, Tuple

from jian_ling.prompts.interview_prompt import JOB_CV_ANALYST_PROMPT

DEFAULT_REJECTION_MESSAGE = (
    "We could not use these inputs. Please upload a CV/resume PDF and paste a real job description."
)


def cv_job_analysis_accepted(payload: Any) -> Tuple[bool, str]:
    """
    Returns (True, empty str) if analysis should proceed, or (False, user_message) if rejected.

    Older model responses without ``inputs_valid`` are treated as accepted for backward compatibility.
    """
    if not isinstance(payload, dict):
        return False, DEFAULT_REJECTION_MESSAGE

    if "inputs_valid" in payload and payload["inputs_valid"] is False:
        reason = payload.get("rejection_reason")
        if isinstance(reason, str) and reason.strip():
            return False, reason.strip()
        return False, DEFAULT_REJECTION_MESSAGE

    return True, ""


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


def analyze_cv_against_job_description(client, cv_file_id, job_description, model="gpt-4.1"):
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

