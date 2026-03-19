from typing import Dict


def compose_prompt(persona: str, task: str, output: str, *, role: str = "system") -> Dict[str, str]:
    """Compose a single prompt message from persona, task, and output blocks."""
    sections = [
        f"Persona:\n{persona.strip()}",
        f"Tasks:\n{task.strip()}",
        f"Output format (required):\n{output.strip()}",
    ]
    content = "\n\n".join(sections).strip()
    return {"role": role, "content": content}
