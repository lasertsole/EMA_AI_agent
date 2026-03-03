"""Skills loader and snapshot builder."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from config import ROOT_DIR, SKILLS_DIR, WORKSPACE_DIR


def _parse_frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    return yaml.safe_load(parts[1]) or {}


def scan_skills() -> list[dict[str, str]]:
    skills: list[dict[str, str]] = []
    for skill_file in SKILLS_DIR.glob("**/SKILL.md"):
        content = skill_file.read_text(encoding="utf-8")
        meta = _parse_frontmatter(content)
        name = str(meta.get("name", skill_file.parent.name))
        desc = str(meta.get("description", ""))
        rel = skill_file.relative_to(ROOT_DIR)
        skills.append(
            {
                "name": name,
                "description": desc,
                "location": f"./{rel.as_posix()}",
            }
        )
    skills.sort(key=lambda x: x["name"])
    return skills


def build_skills_snapshot() -> str:
    skills = scan_skills()
    lines = ["<available_skills>"]
    for s in skills:
        lines.append("  <skill>")
        lines.append(f"    <name>{s['name']}</name>")
        lines.append(f"    <description>{s['description']}</description>")
        lines.append(f"    <location>{s['location']}</location>")
        lines.append("  </skill>")
    lines.append("</available_skills>")
    return "\n".join(lines)


def write_skills_snapshot() -> Path:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    content = build_skills_snapshot()
    path = WORKSPACE_DIR / "SKILLS_SNAPSHOT.md"
    path.write_text(content, encoding="utf-8")
    return path


def get_skills_snapshot_text() -> str:
    path = WORKSPACE_DIR / "SKILLS_SNAPSHOT.md"
    if not path.exists():
        write_skills_snapshot()
    return path.read_text(encoding="utf-8")
