"""Memory entry writing utilities for Claude Code's memory system."""

from pathlib import Path


def write_memory_entry(
    memory_dir: str | Path,
    filename: str,
    name: str,
    description: str,
    memory_type: str,
    body: str,
) -> Path:
    memory_dir = Path(memory_dir)
    memory_dir.mkdir(parents=True, exist_ok=True)

    content = f"""---
name: {name}
description: {description}
type: {memory_type}
---

{body}
"""

    path = memory_dir / filename
    path.write_text(content)
    return path


def update_memory_index(
    memory_dir: str | Path,
    filename: str,
    description: str,
) -> None:
    memory_dir = Path(memory_dir)
    index_path = memory_dir / "MEMORY.md"

    new_line = f"- [{description}]({filename})"

    if index_path.exists():
        lines = index_path.read_text().splitlines()
        updated = False
        for i, line in enumerate(lines):
            if f"({filename})" in line:
                lines[i] = new_line
                updated = True
                break
        if not updated:
            lines.append(new_line)
        index_path.write_text("\n".join(lines) + "\n")
    else:
        index_path.write_text(new_line + "\n")
