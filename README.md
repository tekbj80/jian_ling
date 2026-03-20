# Interview preparation app (jian_ling)

Streamlit app for mock interview practice: upload a CV (PDF), paste a job description, get suitability/gap analysis, then chat with an AI interviewer.

## Setup

```bash
pip install -r requirements.txt
```

Environment variables:

- `OPENAI_API_KEY` — required for CV/JD analysis and for chat when using OpenAI models.
- `DEEPSEEK_API_KEY` — optional; only if you select the DeepSeek provider in the sidebar.

## Run

From the repository root (adjust path if needed):

```bash
streamlit run jian_ling/streamlit_app/interview_app.py
```

## Course alignment

### Prompting techniques (5+)

Task presets live in [`jian_ling/prompts/tasks/interview_tasks.py`](jian_ling/prompts/tasks/interview_tasks.py) (`INTERVIEW_TASK_DICT`). Each maps to a different style in the composed **system** prompt:

| UI label | Technique |
|----------|-----------|
| Gap Critical Analysis | Gap-focused drill-down |
| Suitability Based Analysis | Strengths / match drill-down |
| Few-Shot Behavioral (STAR) | Few-shot |
| CoT Technical Deep Dive | Chain-of-Thought (internal analysis) |
| Zero-Shot Structured JSON | Zero-shot + structured JSON |
| Tree-of-Thought Strategic Interviewer | Tree-of-Thought |
| Self-Consistency with Reflection | Self-critique / reflection |

### OpenAI generation settings

In the sidebar **Generation settings** expander you can tune **temperature** (default `0.7`) and **top_p** (default `1.0`). These are passed through to `chat.completions.create` for the interview chat and the opening question (see [`jian_ling/chat_session.py`](jian_ling/chat_session.py)).

### Security

See [`jian_ling/SECURITY_NOTES.md`](jian_ling/SECURITY_NOTES.md): prompt-based scope policies plus input length limits and PDF type checks.

### Models

OpenAI model choice is restricted to: `gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano`, `gpt-4o`, `gpt-4o-mini` (default `gpt-4.1`).

## Optional benchmarking

[`jian_ling/interview/benchmark.py`](jian_ling/interview/benchmark.py) supports scripted interviewer/interviewee runs and LLM-as-judge evaluation for experiments in Jupyter.
