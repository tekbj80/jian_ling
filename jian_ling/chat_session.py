import json
from typing import Generator, Optional

try:
    from IPython import get_ipython
    from IPython.display import display, Markdown
except ImportError:
    get_ipython = None
    display = None
    Markdown = None

DEFAULT_MODEL = 'deepseek-chat'
JSON_RESPONSE_FORMAT = {"type": "json_object"}


def _completion_kwargs(temperature: Optional[float], top_p: Optional[float]) -> dict:
    extra = {}
    if temperature is not None:
        extra["temperature"] = temperature
    if top_p is not None:
        extra["top_p"] = top_p
    return extra


def get_response(
    message,
    client,
    server_prompt=None,
    model=DEFAULT_MODEL,
    stream=False,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
):
    if server_prompt is None:
        raise ValueError("server_prompt is required.")
    if not isinstance(server_prompt, dict):
        raise TypeError("server_prompt must be a dictionary with 'role' and 'content' keys.")
    if "role" not in server_prompt or "content" not in server_prompt:
        raise ValueError("server_prompt must contain 'role' and 'content' keys.")
    messages = [server_prompt] + message
    sampling = _completion_kwargs(temperature, top_p)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=stream,
            response_format=JSON_RESPONSE_FORMAT,
            **sampling,
        )
    except Exception as exc:
        if "response_format" not in str(exc).lower():
            raise
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=stream,
            **sampling,
        )
    if stream:
        return response
    return response.choices[0].message.content


def list_available_models(client):
    response = client.models.list()
    models = getattr(response, 'data', response)
    return sorted(model.id for model in models if hasattr(model, 'id'))


class Session:
    def __init__(self, client, model=DEFAULT_MODEL):
        self.client = client
        self.model = model
        # Compact history used as model context (assistant turns are summaries).
        self.messages = []
        # Full-fidelity history for UI rendering.
        self.display_messages = []
        self.current_message = None
        self.current_summary = None
        self.current_payload = None
        self.in_jupyter = self._is_jupyter_environment()

    @staticmethod
    def _is_jupyter_environment():
        if get_ipython is None:
            return False

        shell = get_ipython()
        if shell is None:
            return False

        # ZMQInteractiveShell is used by Jupyter notebooks/lab.
        return shell.__class__.__name__ == 'ZMQInteractiveShell'

    @staticmethod
    def _parse_json_payload(raw_content):
        content = raw_content if isinstance(raw_content, str) else str(raw_content or "")
        content = content.strip()
        if not content:
            raise ValueError("Empty model output.")

        # Tolerate fenced JSON if the model ignores formatting instructions.
        if content.startswith('```'):
            lines = content.splitlines()
            if lines and lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            content = '\n'.join(lines).strip()
            if content.lower().startswith('json'):
                content = content[4:].strip()

        payload = json.loads(content)
        if not isinstance(payload, dict):
            raise ValueError('Model output must be a JSON object.')

        if 'response' not in payload or 'summary' not in payload:
            raise ValueError("Model JSON must contain 'response' and 'summary' keys.")

        return payload

    @staticmethod
    def _fallback_payload(raw_content):
        content = (raw_content or '').strip()
        if not content:
            content = "No response content was returned by the model."

        # Keep summary compact for context windows.
        summary = content if len(content) <= 500 else f"{content[:497]}..."
        return {"response": content, "summary": summary}

    def _finalize_payload(self, raw_content):
        try:
            payload = self._parse_json_payload(raw_content)
        except Exception:
            payload = self._fallback_payload(raw_content)

        self.current_payload = payload
        self.current_message = payload['response']
        self.current_summary = payload['summary']
        self.messages.append({'role': 'assistant', 'content': self.current_summary})
        self.display_messages.append({'role': 'assistant', 'content': self.current_message})
        return payload

    def _chat_single(self, message, server_prompt, selected_model):
        raw_content = get_response(
            message=message,
            client=self.client,
            server_prompt=server_prompt,
            model=selected_model,
            stream=False
        )
        payload = self._finalize_payload(raw_content)
        if self.in_jupyter:
            display(Markdown(self.current_message))
        return payload

    def _chat_stream(
        self, message, server_prompt, selected_model, temperature=None, top_p=None
    ) -> Generator[str, None, None]:
        response_stream = get_response(
            message=message,
            client=self.client,
            server_prompt=server_prompt,
            model=selected_model,
            stream=True,
            temperature=temperature,
            top_p=top_p,
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

        full_response = ''.join(collected_chunks)
        self._finalize_payload(full_response)

    def chat(
        self,
        message,
        server_prompt=None,
        model=None,
        stream=False,
        temperature=None,
        top_p=None,
    ):
        message_to_send = {'role': 'user', 'content': message}
        self.messages.append(message_to_send)
        self.display_messages.append(message_to_send)
        selected_model = self.model if model is None else model
        if server_prompt is None:
            raise ValueError("server_prompt is required.")

        if stream:
            return self._chat_stream(
                message=self.messages,
                server_prompt=server_prompt,
                selected_model=selected_model,
                temperature=temperature,
                top_p=top_p,
            )
        return self._chat_single(
            message=self.messages,
            server_prompt=server_prompt,
            selected_model=selected_model,
            temperature=temperature,
            top_p=top_p,
        )
