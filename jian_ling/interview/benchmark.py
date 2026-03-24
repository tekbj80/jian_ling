import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .analysis import (
    analyze_cv_against_job_description,
    cv_job_analysis_accepted,
    parse_analysis_output,
)


PromptLike = Union[str, Dict[str, str]]

DEFAULT_INJECT_INTERVIEWER_INSTRUCTION = (
    "The interviewee's latest line in the transcript may be on-topic, off-topic, or an unrelated question. "
    "Respond in character as the interviewer/coach: address it briefly if needed, then steer back to interview "
    "preparation for this role when appropriate. Keep your reply concise."
)


class InterviewBenchmark:
    """Run interviewer/interviewee benchmark loops and judge the transcript."""

    def __init__(
        self,
        client,
        model: str,
        job_description: str,
        cv_pdf_path: str,
        interviewer_prompt: PromptLike,
        interviewee_prompt: PromptLike,
        analysis_model: str = "gpt-4.1",
    ):
        self.client = client
        self.model = model
        self.analysis_model = analysis_model
        self.job_description = (job_description or "").strip()
        self.cv_pdf_path = Path(cv_pdf_path)
        self.interviewer_prompt = self._normalize_system_prompt(interviewer_prompt, "interviewer_prompt")
        self.interviewee_prompt = self._normalize_system_prompt(interviewee_prompt, "interviewee_prompt")

        if not self.job_description:
            raise ValueError("job_description must be a non-empty string.")
        if not self.cv_pdf_path.exists() or not self.cv_pdf_path.is_file():
            raise ValueError(f"cv_pdf_path does not exist or is not a file: {self.cv_pdf_path}")
        if self.cv_pdf_path.suffix.lower() != ".pdf":
            raise ValueError("cv_pdf_path must point to a .pdf file.")

        self.cv_file_id: str = ""
        self.cv_file_name: str = self.cv_pdf_path.name
        self.job_suitability_analysis: Any = ""
        self.chat_history: List[Dict[str, str]] = []
        self.interviewer_responses: List[str] = []
        self.interviewee_responses: List[str] = []
        self.judged_output: Any = None

    @staticmethod
    def _normalize_system_prompt(prompt: PromptLike, name: str) -> Dict[str, str]:
        if isinstance(prompt, str):
            text = prompt.strip()
            if not text:
                raise ValueError(f"{name} cannot be empty.")
            return {"role": "system", "content": text}

        if isinstance(prompt, dict):
            role = prompt.get("role", "")
            content = (prompt.get("content", "") or "").strip()
            if role != "system" or not content:
                raise ValueError(f"{name} must have role='system' and non-empty content.")
            return {"role": "system", "content": content}

        raise TypeError(f"{name} must be a string or dict prompt.")

    @staticmethod
    def _extract_message_text(response) -> str:
        try:
            text = response.choices[0].message.content
            return (text or "").strip()
        except Exception as exc:
            raise ValueError(f"Could not extract completion text: {exc}") from exc

    def _call_chat(self, system_prompt: Dict[str, str], user_text: str, model: str, force_json: bool = False) -> str:
        request_kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [
                system_prompt,
                {"role": "user", "content": user_text},
            ],
        }
        if force_json:
            request_kwargs["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(**request_kwargs)
        return self._extract_message_text(response)

    def _analysis_as_text(self) -> str:
        if isinstance(self.job_suitability_analysis, dict):
            return json.dumps(self.job_suitability_analysis, ensure_ascii=False)
        return str(self.job_suitability_analysis or "")

    def rebuild_chat_sequence(self) -> str:
        """Return a labeled, ordered transcript suitable for judging."""
        lines = []
        for idx, turn in enumerate(self.chat_history, start=1):
            speaker = turn["speaker"].upper()
            lines.append(f"{idx}. {speaker}: {turn['content']}")
        return "\n".join(lines).strip()

    def prepare_context(self) -> Any:
        """Upload CV PDF and compute suitability/gap analysis once."""
        with self.cv_pdf_path.open("rb") as pdf_file:
            upload = self.client.files.create(file=pdf_file, purpose="user_data")

        self.cv_file_id = upload.id
        self.cv_file_name = getattr(upload, "filename", self.cv_pdf_path.name)

        analysis_response = analyze_cv_against_job_description(
            client=self.client,
            cv_file_id=self.cv_file_id,
            job_description=self.job_description,
            model=self.analysis_model,
        )
        self.job_suitability_analysis = parse_analysis_output(analysis_response)
        ok, msg = cv_job_analysis_accepted(self.job_suitability_analysis)
        if not ok:
            raise ValueError(msg)
        return self.job_suitability_analysis

    def run_interview(self, question_count: int = 5) -> List[Dict[str, str]]:
        """Run interviewer -> interviewee turns and store transcript."""
        if question_count <= 0:
            raise ValueError("question_count must be greater than zero.")

        if not self.job_suitability_analysis:
            self.prepare_context()

        self.chat_history = []
        self.interviewer_responses = []
        self.interviewee_responses = []

        for turn_idx in range(1, question_count + 1):
            transcript = self.rebuild_chat_sequence() or "[no prior turns]"
            interviewer_user_text = "\n\n".join(
                [
                    "Interview context:",
                    f"job_description: <{self.job_description}>",
                    f"job_suitability_analysis: <{self._analysis_as_text()}>",
                    "Current transcript:",
                    transcript,
                    f"Instruction: Ask interview question #{turn_idx}. Ask exactly one question.",
                ]
            )
            interviewer_message = self._call_chat(
                system_prompt=self.interviewer_prompt,
                user_text=interviewer_user_text,
                model=self.model,
            )
            self.interviewer_responses.append(interviewer_message)
            self.chat_history.append({"speaker": "interviewer", "content": interviewer_message})

            transcript = self.rebuild_chat_sequence()
            interviewee_user_text = "\n\n".join(
                [
                    "Interview context:",
                    f"job_description: <{self.job_description}>",
                    f"job_suitability_analysis: <{self._analysis_as_text()}>",
                    "Current transcript:",
                    transcript,
                    "Instruction: Respond as the interview candidate to the latest interviewer question only.",
                ]
            )
            interviewee_message = self._call_chat(
                system_prompt=self.interviewee_prompt,
                user_text=interviewee_user_text,
                model=self.model,
            )
            self.interviewee_responses.append(interviewee_message)
            self.chat_history.append({"speaker": "interviewee", "content": interviewee_message})

        return self.chat_history

    def inject_interviewee_message(
        self,
        message: str,
        *,
        model: Optional[str] = None,
        interviewer_instruction: Optional[str] = None,
    ) -> str:
        """
        Append a **human** interviewee line to the transcript, then fetch the interviewer's next reply.

        Use this to inject your own candidate messages (including unrelated or adversarial prompts) and
        observe how the interviewer model behaves.

        Requires ``job_suitability_analysis`` (call :meth:`prepare_context` or :meth:`run_interview` first).

        Args:
            message: Text spoken by the interviewee/candidate.
            model: Optional model override for this interviewer turn.
            interviewer_instruction: Override the default follow-up instruction to the interviewer.

        Returns:
            The interviewer's response text.
        """
        text = (message or "").strip()
        if not text:
            raise ValueError("message must be a non-empty string.")
        if not self.job_suitability_analysis:
            raise ValueError(
                "No analysis context loaded. Call prepare_context() or run_interview() before injecting messages."
            )

        self.chat_history.append({"speaker": "interviewee", "content": text})
        self.interviewee_responses.append(text)

        instruction = (interviewer_instruction or DEFAULT_INJECT_INTERVIEWER_INSTRUCTION).strip()
        interviewer_user_text = "\n\n".join(
            [
                "Interview context:",
                f"job_description: <{self.job_description}>",
                f"job_suitability_analysis: <{self._analysis_as_text()}>",
                "Current transcript:",
                self.rebuild_chat_sequence(),
                "Instruction:",
                instruction,
            ]
        )
        selected_model = model or self.model
        interviewer_message = self._call_chat(
            system_prompt=self.interviewer_prompt,
            user_text=interviewer_user_text,
            model=selected_model,
        )
        self.interviewer_responses.append(interviewer_message)
        self.chat_history.append({"speaker": "interviewer", "content": interviewer_message})
        return interviewer_message

    def judge_chat(self, judge_prompt: PromptLike, judge_model: str = "") -> Any:
        """
        Public method to judge transcript quality.
        Expects judge prompt to return JSON.
        """
        if not self.chat_history:
            raise ValueError(
                "No chat history found. Run run_interview() and/or inject_interviewee_message() first."
            )

        judge_system_prompt = self._normalize_system_prompt(judge_prompt, "judge_prompt")
        model = judge_model or self.model

        judge_user_text = "\n\n".join(
            [
                "Evaluate this interview transcript.",
                "Context:",
                f"job_description: <{self.job_description}>",
                f"job_suitability_analysis: <{self._analysis_as_text()}>",
                "Transcript (ordered):",
                self.rebuild_chat_sequence(),
                "Return JSON only.",
            ]
        )

        raw_judgment = self._call_chat(
            system_prompt=judge_system_prompt,
            user_text=judge_user_text,
            model=model,
            force_json=True,
        )
        try:
            self.judged_output = json.loads(raw_judgment)
        except Exception:
            self.judged_output = raw_judgment
        return self.judged_output

