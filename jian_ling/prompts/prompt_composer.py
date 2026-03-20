from typing import Dict


def compose_prompt(
    persona: str,
    task: str,
    output: str,
    *,
    role: str = "system",
    policy: str = "",
) -> Dict[str, str]:
    """Compose a single prompt message from persona, optional safety policy, task, and output blocks."""
    sections = [f"Persona:\n{persona.strip()}"]
    policy_text = (policy or "").strip()
    if policy_text:
        sections.append(f"Safety and scope:\n{policy_text}")
    sections.extend(
        [
            f"Tasks:\n{task.strip()}",
            f"Output format (required):\n{output.strip()}",
        ]
    )
    content = "\n\n".join(sections).strip()
    return {"role": role, "content": content}
