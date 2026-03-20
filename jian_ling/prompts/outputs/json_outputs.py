JOB_CV_ANALYSIS_JSON_OUTPUT = """
Respond in JSON only, with exactly these keys:
{
  "inputs_valid": true or false,
  "rejection_reason": "when inputs_valid is false, one or two short sentences for the user explaining what is wrong (wrong file type of content, or text is not a job posting). When inputs_valid is true, use an empty string \"\".",
  "gaps": "when inputs_valid is true: numbered list of gaps with a keyword at the start of each point. When false: empty string \"\".",
  "suitability": "when inputs_valid is true: numbered list of suitability points with a keyword at the start of each point. When false: empty string \"\"."
}

Validation rules (set inputs_valid to false if any fail):
- The PDF must plausibly be a CV or resume (work history, education, skills, contact header, etc.). Reject if it is clearly not a CV (e.g. unrelated document, blank, or non-professional content that cannot be treated as a resume).
- The job description text must plausibly be a job posting or role specification (title, responsibilities, requirements, qualifications). Reject if it is clearly not a JD (e.g. random text, personal chat, unrelated article).

If either input fails, do not invent gaps or suitability; use empty strings for those fields and a helpful rejection_reason.
""".strip()

RESPONSE_SUMMARY_JSON_OUTPUT = """
Return exactly one JSON object with keys:
- response: the entire response you make to the user.
- summary: a summary of your response.
""".strip()
