"""Tests for install.py: sentinel injection, skill copy, and idempotency.

All tests use tmp_path / a monkeypatched Path.home() so they never touch the
real ~/.claude/.
"""

from __future__ import annotations

from pathlib import Path

import install as installer
import pytest
from install import (
    BEGIN,
    END,
    CorruptedMarkerError,
    apply_block,
    install,
    install_skills,
    main,
)

# --- apply_block: the three marker states -----------------------------------


def test_apply_block_both_markers_present_replaces_between() -> None:
    existing = f"before\n\n{BEGIN}\nold body\n{END}\n\nafter"
    result = apply_block(existing, "new body")
    assert result == f"before\n\n{BEGIN}\nnew body\n{END}\n\nafter"


def test_apply_block_neither_marker_present_appends() -> None:
    existing = "some notes the user wrote"
    result = apply_block(existing, "new body")
    assert result == f"some notes the user wrote\n\n{BEGIN}\nnew body\n{END}\n"


def test_apply_block_neither_marker_present_empty_existing() -> None:
    result = apply_block("", "new body")
    assert result == f"{BEGIN}\nnew body\n{END}\n"


def test_apply_block_exactly_one_marker_raises() -> None:
    existing = f"before\n{BEGIN}\nold body\nafter, no end marker"
    with pytest.raises(CorruptedMarkerError):
        apply_block(existing, "new body")


def test_apply_block_only_end_marker_raises() -> None:
    existing = f"before\nold body\n{END}\nafter"
    with pytest.raises(CorruptedMarkerError):
        apply_block(existing, "new body")


def test_apply_block_idempotent() -> None:
    once = apply_block("notes", "body text")
    twice = apply_block(once, "body text")
    assert once == twice


# --- install(): full orchestration against a fake home ----------------------


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    return tmp_path / "home"


def test_install_creates_memory_file_and_claude_dir(fake_home: Path) -> None:
    claude_dir = fake_home / ".claude"
    assert not claude_dir.exists()

    code = install(claude_dir)

    assert code == 0
    memory_file = claude_dir / "CLAUDE.md"
    assert memory_file.exists()
    text = memory_file.read_text()
    assert BEGIN in text
    assert END in text
    assert "jira-tools" in text


def test_install_copies_skills(fake_home: Path) -> None:
    claude_dir = fake_home / ".claude"

    installed = install_skills(installer.SKILLS_SRC, claude_dir)

    assert "assemble-ticket-context" in installed
    target = claude_dir / "skills" / "assemble-ticket-context" / "SKILL.md"
    assert target.exists()
    source = installer.SKILLS_SRC / "assemble-ticket-context" / "SKILL.md"
    assert target.read_text() == source.read_text()


def test_install_skills_removes_stale_files(fake_home: Path) -> None:
    claude_dir = fake_home / ".claude"
    target_dir = claude_dir / "skills" / "assemble-ticket-context"
    target_dir.mkdir(parents=True)
    stale_file = target_dir / "stale.md"
    stale_file.write_text("leftover from a previous version")

    install_skills(installer.SKILLS_SRC, claude_dir)

    assert not stale_file.exists()


def test_install_is_idempotent(fake_home: Path) -> None:
    claude_dir = fake_home / ".claude"

    install(claude_dir)
    memory_file = claude_dir / "CLAUDE.md"
    first_memory = memory_file.read_text()
    first_skill = (claude_dir / "skills" / "assemble-ticket-context" / "SKILL.md").read_text()

    install(claude_dir)
    second_memory = memory_file.read_text()
    second_skill = (claude_dir / "skills" / "assemble-ticket-context" / "SKILL.md").read_text()

    assert first_memory == second_memory
    assert first_skill == second_skill


def test_install_preserves_hand_edited_notes(fake_home: Path) -> None:
    claude_dir = fake_home / ".claude"
    claude_dir.mkdir(parents=True)
    memory_file = claude_dir / "CLAUDE.md"
    memory_file.write_text("# My personal notes\n\nSome stuff I wrote.\n")

    install(claude_dir)

    text = memory_file.read_text()
    assert "# My personal notes" in text
    assert "Some stuff I wrote." in text
    assert BEGIN in text


def test_install_refuses_on_corrupted_block(fake_home: Path) -> None:
    claude_dir = fake_home / ".claude"
    claude_dir.mkdir(parents=True)
    memory_file = claude_dir / "CLAUDE.md"
    corrupted = f"notes\n{BEGIN}\nold block, end marker missing\n"
    memory_file.write_text(corrupted)

    code = install(claude_dir)

    assert code != 0
    assert memory_file.read_text() == corrupted


def test_main_uses_home_dot_claude(monkeypatch: pytest.MonkeyPatch, fake_home: Path) -> None:
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    code = main()

    assert code == 0
    assert (fake_home / ".claude" / "CLAUDE.md").exists()
    assert (fake_home / ".claude" / "skills" / "assemble-ticket-context" / "SKILL.md").exists()


def test_install_output_has_no_secret_material(
    fake_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    claude_dir = fake_home / ".claude"

    install(claude_dir)

    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "api_token" not in output
    assert "site_url" not in output
    for line in output.splitlines():
        if line.strip():
            assert str(claude_dir) in line or "Updated" in line or "Installed" in line
