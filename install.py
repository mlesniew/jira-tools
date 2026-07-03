"""Installer: copies skills/ into ~/.claude/skills/ and injects jira-tools
usage instructions into ~/.claude/CLAUDE.md between sentinel markers.

Idempotent: running this twice produces the same result. Never reads or
prints config/secret material — only file paths and marker status.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

BEGIN = "<!-- BEGIN jira-tools -->"
END = "<!-- END jira-tools -->"

REPO_ROOT = Path(__file__).resolve().parent
SKILLS_SRC = REPO_ROOT / "skills"
RULES_FILE = REPO_ROOT / "rules" / "jira-tools.md"


class CorruptedMarkerError(Exception):
    """Raised when exactly one sentinel marker is present in the target file."""


def apply_block(existing_text: str, block_body: str) -> str:
    """Idempotently inject block_body between sentinel markers in existing_text.

    Both markers present -> replace only the text between them, preserving the
    rest verbatim. Neither present -> append after the existing content
    (trimmed of trailing whitespace), creating from empty if needed. Exactly
    one present -> raise CorruptedMarkerError.
    """
    start = existing_text.find(BEGIN)
    end = existing_text.find(END)

    if start != -1 and end != -1:
        before = existing_text[:start]
        after = existing_text[end + len(END) :]
        return f"{before}{BEGIN}\n{block_body.strip()}\n{END}{after}"

    if start == -1 and end == -1:
        block = f"{BEGIN}\n{block_body.strip()}\n{END}\n"
        trimmed = existing_text.rstrip()
        return f"{trimmed}\n\n{block}" if trimmed else block

    raise CorruptedMarkerError(
        "Only one of the jira-tools sentinel markers was found in "
        "the target file; fix it by hand before re-running the installer."
    )


def install_skills(skills_src: Path, claude_dir: Path) -> list[str]:
    """Mirror each skills_src/<name>/ into claude_dir/skills/<name>/, removing
    any stale target first. Returns the names of the skills installed."""
    target_skills = claude_dir / "skills"
    target_skills.mkdir(parents=True, exist_ok=True)

    installed = []
    for skill_dir in sorted(p for p in skills_src.iterdir() if p.is_dir()):
        target = target_skills / skill_dir.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(skill_dir, target)
        installed.append(skill_dir.name)
    return installed


def install_memory_block(rules_file: Path, memory_file: Path) -> None:
    """Inject rules_file's content into memory_file between sentinel markers,
    creating memory_file (and its parent dir) if missing."""
    memory_file.parent.mkdir(parents=True, exist_ok=True)
    existing = memory_file.read_text() if memory_file.exists() else ""
    block_body = rules_file.read_text()
    memory_file.write_text(apply_block(existing, block_body))


def install(claude_dir: Path) -> int:
    """Run the full install against claude_dir (normally ~/.claude). Returns
    a process exit code."""
    installed = install_skills(SKILLS_SRC, claude_dir)
    for name in installed:
        print(f"Installed skill: {claude_dir / 'skills' / name}")

    memory_file = claude_dir / "CLAUDE.md"
    try:
        install_memory_block(RULES_FILE, memory_file)
    except CorruptedMarkerError as exc:
        print(f"Could not update {memory_file}: {exc}", file=sys.stderr)
        return 1

    print(f"Updated global memory: {memory_file}")
    return 0


def main() -> int:
    return install(Path.home() / ".claude")


if __name__ == "__main__":
    raise SystemExit(main())
