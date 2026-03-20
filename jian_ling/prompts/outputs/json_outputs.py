JOB_CV_ANALYSIS_JSON_OUTPUT = """
Respond in JSON only:
{
  "gaps": "numbered list that describes gaps with a keyword at the start of each point",
  "suitability": "numbered list with a keyword that describes suitability points"
}
""".strip()

RESPONSE_SUMMARY_JSON_OUTPUT = """
Return exactly one JSON object with keys:
- response: the entire response you make to the user.
- summary: a summary of your response.
""".strip()
