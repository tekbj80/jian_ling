# Interview app — security / misuse prevention

This app uses **defense in depth** for the course requirement to add a guard against misuse:

1. **Prompt policy** — `INTERVIEWER_SAFETY_POLICY` and `ANALYST_SAFETY_POLICY` in [`prompts/guards/interview_safety.py`](prompts/guards/interview_safety.py) are injected into composed system prompts via [`prompts/prompt_composer.py`](prompts/prompt_composer.py) (section **Safety and scope**). They limit scope to interview prep / CV–JD analysis and instruct the model to refuse common abuse patterns and prompt-injection-style overrides.

2. **Input validation** — [`streamlit_app/interview_app.py`](streamlit_app/interview_app.py) enforces a maximum length on the job description (**8000** characters) before analysis. Chat uses `st.chat_input(..., max_chars=8000)` (Streamlit **1.33+**) so the client stops accepting input at the limit. This reduces accidental huge pastes, cost spikes, and context blow-ups. PDF upload is already restricted to `.pdf`.

These measures are **not** a substitute for production auth, rate limiting, or content moderation services.
