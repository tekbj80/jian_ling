from .guards import ANALYST_SAFETY_POLICY, INTERVIEWER_SAFETY_POLICY
from .outputs import json_outputs as j_output
from .personas import interview_personas as persona
from .prompt_composer import compose_prompt
from .tasks import interview_tasks as task

JOB_CV_ANALYST_PROMPT = compose_prompt(
    persona=persona.FRIENDLY_HR_PERSON.strip(),
    task=task.JOB_CV_ANALYSIS_TASK,
    output=j_output.JOB_CV_ANALYSIS_JSON_OUTPUT,
    policy=ANALYST_SAFETY_POLICY,
)


def build_session_summary_prompt(job_description: str, job_suitability_analysis: str) -> dict:
    """
    One-shot system prompt: summarize the candidate's answers from a full transcript.
    job_suitability_analysis may be structured JSON/dict string or plain text.
    """
    task = "\n\n".join(
        [
            "The user message contains the full mock-interview transcript so far. "
            "User turns are the candidate; assistant turns are the interviewer/coach.",
            "Your job:",
            "1. Summarize the candidate's answers: main themes, examples, and STAR coverage "
            "(Situation, Task, Action, Result) where relevant.",
            "2. Give clear feedback on strengths and recurring gaps across their answers.",
            "3. Give concrete, actionable suggestions for how they could improve for a real "
            "interview for this role.",
            "4. Anchor your comments to the job description and suitability/gap analysis below.",
            "Speak only in English.",
            "Context:",
            f"job_description: <{job_description}>",
            f"job_suitability_analysis: <{job_suitability_analysis}>",
        ]
    ).strip()
    return compose_prompt(
        persona=persona.FRIENDLY_HR_PERSON.strip(),
        task=task,
        output=j_output.RESPONSE_SUMMARY_JSON_OUTPUT,
        policy=INTERVIEWER_SAFETY_POLICY,
    )


def build_interviewer_prompt(
    job_description: str,
    job_suitability_analysis: str,
    selected_task: str,
    selected_persona: str,
) -> dict:
    interview_task = "\n\n".join(
        [
            "Instruction: When user gives you an answer, give them a feedback on their answer, and give ideas on how to improve their answers.",
            "Instruction: Speak only in English.",
            selected_task.strip(),
            "Context:",
            f"job_description: <{job_description}>",
            f"job_suitability_analysis: <{job_suitability_analysis}>",
            
        ]
    ).strip()
    return compose_prompt(
        persona=selected_persona,
        task=interview_task,
        output=j_output.RESPONSE_SUMMARY_JSON_OUTPUT,
        policy=INTERVIEWER_SAFETY_POLICY,
    )

