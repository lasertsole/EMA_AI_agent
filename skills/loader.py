"""Skills loader and snapshot builder."""

from __future__ import annotations

from typing import Any, List, Optional

import yaml

from config import ROOT_DIR, SKILLS_DIR


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


def get_skills_text(selected_skill_names: Optional[List[str]]=None) -> str:
    skills = scan_skills()

    if selected_skill_names is not None and len(selected_skill_names) > 0:
        skills = [s for s in skills if s["name"] in selected_skill_names]

    lines = ["<available_skills>"]
    for s in skills:
        lines.append("  <skill>")
        lines.append(f"    <name>{s['name']}</name>")
        lines.append(f"    <description>{s['description']}</description>")
        lines.append(f"    <location>{s['location']}</location>")
        lines.append("  </skill>")
    lines.append("</available_skills>")
    return "\n".join(lines)
