# Interview prep app — prompt library & composition (reviewer brief)

Short walkthrough of **how prompts are organized** and **assembled into system messages** for the Sprint 1 interview-prep project.

---

## 1. What the product does

- User uploads a **CV (PDF)** and pastes a **job description**.
- OpenAI runs a **CV vs JD analysis** (gaps + suitability, structured JSON).
- A **mock interview chat** uses a composed **system prompt** (persona + task style + context + output contract).
- Optional: **benchmark** loop (simulated interviewee + **LLM-as-judge**) for comparing prompt techniques.

---

## 2. Design idea: a prompt *library*, not one giant string

Instead of one monolithic prompt file, content is split by **role**:

| Layer | Responsibility | Location (examples) |
|--------|----------------|----------------------|
| **Persona** | Tone, role (“friendly HR”, “historical persona”, …) | `jian_ling/prompts/personas/` |
| **Task** | *What* to do (interview style, few-shot, CoT, gap vs fit focus, …) | `jian_ling/prompts/tasks/` |
| **Output** | Required format (JSON schema, plain text rules) | `jian_ling/prompts/outputs/` |
| **Safety / scope** | Misuse prevention, stay on mission | `jian_ling/prompts/guards/` |
| **Composition** | Glue blocks into one `system` message | `jian_ling/prompts/prompt_composer.py` |
| **Recipes** | Concrete prompts for each API use case | `jian_ling/prompts/interview_prompt.py` |

This makes it easy to **swap personas and task techniques** in the UI without duplicating safety or JSON rules.

---

## 3. How assembly works: `compose_prompt`

All “full” system prompts are built through **`compose_prompt`** in `prompt_composer.py`:

```text
┌─────────────────────────────────────────────────────────────┐
│  System message content (single string)                      │
├─────────────────────────────────────────────────────────────┤
│  1. Persona:          …who you are / how you sound           │
│  2. Safety and scope: …optional; interview misuse guard      │
│  3. Tasks:            …instructions + injected context       │
│  4. Output format:    …JSON-only rules, keys, constraints    │
└─────────────────────────────────────────────────────────────┘
```

**API shape:** `compose_prompt(persona, task, output, policy=..., role="system")`  
→ returns `{"role": "system", "content": "<assembled markdown>"}`.

So the **library** is the building blocks; **composition** is deterministic string assembly in code.

---

## 4. Two main composed “products”

### A. JD + CV analyst — `JOB_CV_ANALYST_PROMPT`

Defined in `interview_prompt.py`:

- **Persona:** e.g. friendly HR-style analyst (`interview_personas`)
- **Task:** `JOB_CV_ANALYSIS_TASK` (`interview_tasks.py`) — validate inputs + compare CV to JD
- **Output:** `JOB_CV_ANALYSIS_JSON_OUTPUT` (`json_outputs.py`) — includes `inputs_valid`, `rejection_reason`, `gaps`, `suitability`
- **Policy:** `ANALYST_SAFETY_POLICY` (`guards/interview_safety.py`)

Used by the **OpenAI Responses API** (file + text) in `jian_ling/interview/analysis.py`.

### B. Live interviewer — `build_interviewer_prompt(...)`

Also in `interview_prompt.py`:

- **Persona:** user-selected string (from Streamlit)
- **Task:** built from:
  - fixed instructions (feedback, language, …),
  - **selected task block** from the task library,
  - **runtime context:** `job_description` + `job_suitability_analysis`
- **Output:** `RESPONSE_SUMMARY_JSON_OUTPUT` — assistant returns JSON with `response` + `summary` (chat session uses this for UI + compact history)
- **Policy:** `INTERVIEWER_SAFETY_POLICY`

The **task block** is what changes when the user picks “Few-shot”, “CoT”, “Zero-shot JSON”, etc.

---

## 5. Task library = multiple prompting *techniques*

`jian_ling/prompts/tasks/interview_tasks.py` holds **named task strings** (each embodies a technique or focus), e.g.:

- Gap-focused vs suitability-focused flows  
- **Few-shot** behavioral (STAR examples)  
- **Chain-of-Thought** (internal `<analysis>` then one question)  
- **Zero-shot** structured JSON coach output  
- **Tree-of-Thought** (compare strategies, pick one)  
- **Self-consistency / reflection** (draft → check criteria → revise)

They are exposed as a single dict for the UI:

```text
INTERVIEW_TASK_DICT  →  Streamlit “Task” dropdown (no hardcoding in the app)
```

So the course requirement “**≥5 system prompts with different techniques**” is satisfied by **composing** the same skeleton with **different task modules** — each combination is a distinct system prompt in practice.

---

## 6. Supporting prompt modules (benchmark / eval)

| File | Role |
|------|------|
| `tasks/interviewee.py` | Simulated candidate behavior |
| `tasks/judge.py` | LLM-as-judge rubric (JSON scores) |
| `outputs/simple.py` | Plain-text output contract for interviewee |

These reuse the same **split-by-concern** idea; benchmark code lives under `jian_ling/interview/benchmark.py`.

---

## 7. End-to-end flow (Streamlit)

```text
User: PDF + JD
    → analysis: JOB_CV_ANALYST_PROMPT (+ validation fields)
    → if inputs_valid: build_interviewer_prompt(persona, task from INTERVIEW_TASK_DICT, context)
    → chat: Session + streaming completions (temperature / top-p from sidebar)
```

---

## 8. Why this is nice for reviewers

1. **Traceability** — Every system message is built from **named, versioned blocks**.  
2. **Experimentation** — Swap **task** or **persona** without touching safety or JSON schema.  
3. **Course alignment** — Clear mapping from **prompting techniques** to **menu entries** and code paths.  
4. **Extensibility** — New technique = new constant in `interview_tasks.py` + one line in `INTERVIEW_TASK_DICT`.

---

## 9. Course requirements — coverage (traceability)

**Legend:** **Yes** = implemented in repo · **Partial** = partly / depends on your write-up or host · **You** = your responsibility outside code (e.g. keys, reflection doc)

### Official task requirements

| Requirement | Status | Where / notes |
|-------------|--------|----------------|
| Research & creative interview-prep angle | **Yes** | CV+JD gap/suitability, personas, multi-technique tasks, opening question after analysis |
| Front-end (Streamlit vs Next) | **Yes** | `jian_ling/streamlit_app/interview_app.py` |
| Create / use OpenAI API key | **You** | Env `OPENAI_API_KEY`; not stored in repo |
| Use an allowed model (4.1 family / 4o family) | **Yes** | Allowlist + default in `interview_app.py`; analysis + chat |
| ≥5 system prompts / techniques (few-shot, CoT, zero-shot, …) | **Yes** | `interview_tasks.py` + `INTERVIEW_TASK_DICT`; composed via `build_interviewer_prompt` |
| Tune ≥1 OpenAI parameter (temperature, top-p, …) | **Yes** | Sidebar sliders → `chat_session.get_response` / `Session.chat`; opening turn in `helpers.py` |
| ≥1 security guard against misuse | **Yes** | `guards/interview_safety.py` in composed prompts; JD/chat length limits; PDF type; optional analyst `inputs_valid` rejection |

### Optional tasks (selected)

| Optional item | Status | Where / notes |
|---------------|--------|----------------|
| **Easy** — Personas / domain tone | **Yes** | `personas/interview_personas.py` + Streamlit selector |
| **Easy** — More security constraints | **Partial** | Prompt guards + validation; no second LLM verifier |
| **Easy** — Difficulty levels (easy/med/hard) | **Partial** | Gap vs suitability tasks imply focus, not explicit difficulty slider |
| **Medium** — All OpenAI settings as sliders | **Partial** | Model + temperature + top-p; no frequency penalty / presence sliders |
| **Medium** — ≥2 structured JSON formats | **Yes** | CV analysis JSON (`json_outputs.py`); chat `response`+`summary` JSON |
| **Medium** — Deploy app | **Partial** | `pyproject.toml` + `requirements.txt` (`-e .`); depends if you deployed Streamlit Cloud |
| **Medium** — Price of prompt | **No** | Not implemented |
| **Medium** — Jailbreak experiment + Excel | **No** | Not in repo; `inject_interviewee_message` in `benchmark.py` helps you run manual tests |
| **Medium** — RAG / extra JD field | **Partial** | JD text field; not vector RAG |
| **Medium** — Multiple LLM providers | **Partial** | OpenAI + DeepSeek option in sidebar; not Gemini |
| **Hard** — Full chatbot (multi-turn) | **Yes** | `Session` + streaming + history |
| **Hard** — LLM-as-judge / assess prompts | **Yes** | `tasks/judge.py`, `InterviewBenchmark.judge_chat` |

### Evaluation criteria (rubric alignment)

| Criterion | Status | Notes |
|-----------|--------|--------|
| Explain prompting techniques | **You** | This doc + `INTERVIEW_TASK_DICT` names support your explanation |
| Understand temperature / top-p | **Yes** | Implemented; explain defaults in reflection |
| User / system / assistant roles | **Yes** | Composed `system`; user content in API + Streamlit |
| Different output types (e.g. JSON) | **Yes** | Analysis JSON vs chat JSON vs plain interviewee (`outputs/simple.py`) |
| App works for interview prep | **Yes** | End-to-end Streamlit flow |
| Correct OpenAI API usage | **Yes** | Responses API (file+JD); Chat Completions (interview) |
| Front-end library for UI | **Yes** | Streamlit |
| Reflection & improvements | **You** | Written submission; problems/limitations in prose |
| **Bonus:** ≥2 medium + 1 hard optional | **Yes** *if* you count | e.g. dual JSON + (partial) settings + chatbot + judge — confirm with your grader’s list |

---

*Generated for handoff / demo; adjust file paths if your fork layout differs.*
