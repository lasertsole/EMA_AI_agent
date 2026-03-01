"""Skills Scanner - Scan skills/ directory and generate SKILLS_SNAPSHOT.md."""
from pathlib import Path
import yaml

def scan_skills(base_dir: Path) -> str:
    """scan all SKILL.md files and generate SKILLS_SNAPSHOT.md."""
    skills_dir = base_dir / "skills"
    snapshot_path = base_dir / "SKILLS_SNAPSHOT.md"

    if not skills_dir.exists():
        skills_dir.mkdir(parents = True)

    skills = []
    for skill_md in sorted(skills_dir.rglob("SKILL.md")):
        try:
            content = skill_md.read_text(encoding = "utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    meta = yaml.safe_load(parts[1])
                    if meta:
                        rel_path = f"./backend/skills/{skill_md.parent.name}/SKILL.md"
                        skills.append({
                            "name": meta.get("name", skill_md.parent.name),
                            "description": meta.get("description", ""),
                            "location": rel_path,
                        })
        except Exception as e:
            print(f"Error processing {skill_md}: {e}")

    lines = ["<available_skills>"]
    for s in skills:
        lines.append(f" <skill>")
        lines.append(f"     <name>{s['name']}</name>")
        lines.append(f"     <description>{s['description']}</description>")
        lines.append(f"     <location>{s['location']}</location>")
        lines.append(f" </skill>")
    lines.append(f"</available_skills>")

    snapshot = "\n".join(lines)
    snapshot_path.write_text(snapshot, encoding = "utf-8")
    print(f"Skills snapshot: {len(skills)} skills found")
    return snapshot