"""Interview-specific helpers that use a generic Session without putting domain logic on Session."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Generator, Optional, Union

from jian_ling.chat_session import get_response

if TYPE_CHECKING:
    from jian_ling.chat_session import Session

DEFAULT_OPENING_USER_MESSAGE = (
    "The interview session has started. The candidate is ready. "
    "Ask exactly one first interview question based on the job description and suitability/gap analysis."
)


def run_interviewer_opening_turn(
    session: "Session",
    server_prompt: Dict[str, str],
    *,
    model: Optional[str] = None,
    stream: bool = False,
    hidden_user_content: Optional[str] = None,
) -> Union[dict, Generator[str, None, None]]:
    """
    First interviewer turn after CV/JD analysis.

    Appends a synthetic user message only to ``session.messages`` (not ``display_messages``)
    so the UI can show the opening question alone. Then runs one completion and records the
    assistant turn on the session via the same finalize path as ``Session.chat``.

    Args:
        session: Active chat session (typically empty display history).
        server_prompt: ``{"role": "system", "content": ...}`` interviewer system prompt.
        model: Override model; defaults to ``session.model``.
        stream: If True, returns a generator of text chunks (finalize runs after stream ends).
        hidden_user_content: Override the synthetic user message sent to the API only.
    """
    if server_prompt is None:
        raise ValueError("server_prompt is required.")

    kickoff = (hidden_user_content or DEFAULT_OPENING_USER_MESSAGE).strip()
    if not kickoff:
        raise ValueError("hidden_user_content cannot be empty.")

    session.messages.append({"role": "user", "content": kickoff})
    selected_model = session.model if model is None else model

    if stream:

        def _stream() -> Generator[str, None, None]:
            response_stream = get_response(
                message=session.messages,
                client=session.client,
                server_prompt=server_prompt,
                model=selected_model,
                stream=True,
            )
            collected_chunks = []
            for chunk in response_stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                text = getattr(delta, "content", None)
                if text:
                    collected_chunks.append(text)
                    yield text
            full_response = "".join(collected_chunks)
            session._finalize_payload(full_response)

        return _stream()

    raw_content = get_response(
        message=session.messages,
        client=session.client,
        server_prompt=server_prompt,
        model=selected_model,
        stream=False,
    )
    return session._finalize_payload(raw_content)
