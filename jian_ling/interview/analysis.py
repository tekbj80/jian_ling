import json

from jian_ling.prompts.interview_prompt import JOB_CV_ANALYST_PROMPT


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

