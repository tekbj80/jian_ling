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

