"""
export_skill_md.py

Export SKILL nodes from the skill_memory knowledge graph into SKILL.md files
under skills/inferred/<node-name>/SKILL.md.

For each SKILL node:
  - Fetch edges_from() + edges_to() to understand relationships
  - Group edges by type with proper direction semantics
  - Extract instruction/condition fields for routing information
  - Generate YAML frontmatter (name + description) + body sections
  - Write to skills/inferred/<normalized-name>/SKILL.md

BYPASSES context_engine/__init__.py to avoid transitive instructor dependency.
Uses direct SQLite queries instead of importing store modules.
"""

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

# --- Path setup --------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parents[3]  # EMA_AI_agent/
SKILL_MEMORY_PATH = ROOT_DIR / "context_engine" / "skill_memory"
SRC_DIR = ROOT_DIR / "src"
SKILLS_DIR = ROOT_DIR / "skills"
PROJECTION_DIR = SKILLS_DIR / "projection"

DB_PATH = SRC_DIR / "store" / "skill_memory" / "skill_memory.db"


# --- Inline data models (mirrors GmNode / GmEdge from type.py) --------------
class GmNode:
    def __init__(self, row: dict[str, Any]):
        self.id: str = row["id"]
        self.type: str = row["type"]
        self.name: str = row["name"]
        self.description: str = row.get("description") or ""
        self.content: str = row.get("content") or ""
        self.validated_count: int = row.get("validated_count", 1)
        self.source_sessions: list[str] = json.loads(row["source_sessions"]) if row.get("source_sessions") else []
        self.community_id: str | None = row.get("community_id")
        self.pagerank: float = row.get("pagerank", 0.0) or 0.0
        self.created_at: int = row.get("created_at", 0)
        self.updated_at: int = row.get("updated_at", 0)


class GmEdge:
    def __init__(self, row: dict[str, Any]):
        self.id: str = row["id"]
        self.from_id: str = row["from_id"]
        self.to_id: str = row["to_id"]
        self.type: str = row["type"]
        self.instruction: str = row.get("instruction") or ""
        self.condition: str | None = row.get("condition")
        self.session_id: str | None = row.get("session_id")
        self.created_at: int = row.get("created_at", 0)


# --- Helpers (mirrors store/core.py logic) -----------------------------------
def normalize_name(name: str) -> str:
    """Normalize node name to a filesystem-safe identifier."""
    name = name.strip().lower()
    name = re.sub(r'[\s_]+', '-', name)
    name = re.sub(r'[^a-z0-9\u4e00-\u9fff\-]', '', name)
    name = re.sub(r'-{2,}', '-', name)
    return name.strip('-')


def get_db() -> sqlite3.Connection:
    """Open SQLite connection (WAL mode, row factory)."""
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    return db


def edges_from(db: sqlite3.Connection, node_id: str) -> list[GmEdge]:
    """Get all edges starting from the specified node."""
    rows = db.execute("SELECT * FROM gm_edges WHERE from_id=?", (node_id,)).fetchall()
    return [GmEdge(dict(row)) for row in rows]


def edges_to(db: sqlite3.Connection, node_id: str) -> list[GmEdge]:
    """Get all edges pointing to the specified node."""
    rows = db.execute("SELECT * FROM gm_edges WHERE to_id=?", (node_id,)).fetchall()
    return [GmEdge(dict(row)) for row in rows]


def find_by_id(db: sqlite3.Connection, node_id: str) -> GmNode | None:
    """Look up a node by its ID."""
    row = db.execute("SELECT * FROM gm_nodes WHERE id=?", (node_id,)).fetchone()
    return GmNode(dict(row)) if row else None


# --- Edge type labels ---------------------------------------------------------
EDGE_LABELS = {
    "USED_SKILL": "Used By Tasks",
    "SOLVED_BY": "Solves Events",
    "REQUIRES": "Requires",
    "PATCHES": "Patches / Replaces",
    "CONFLICTS_WITH": "Conflicts With",
}


def edge_direction_annotation(etype: str, from_name: str, to_name: str) -> str:
    """Return a human-readable direction label for an edge."""
    direction_map = {
        "USED_SKILL": f"Task `{from_name}` → Skill `{to_name}`",
        "SOLVED_BY": f"Event `{from_name}` → Skill `{to_name}`",
        "REQUIRES": f"Skill `{from_name}` → Skill `{to_name}` (prerequisite)",
        "PATCHES": f"Skill `{from_name}` → Skill `{to_name}` (corrects/improves)",
        "CONFLICTS_WITH": f"Skill `{from_name}` ↔ Skill `{to_name}` (mutually exclusive)",
    }
    return direction_map.get(etype, f"{from_name} → {to_name}")


# --- Edge collection ----------------------------------------------------------
def collect_edges(db: sqlite3.Connection, skill_node: GmNode, node_cache: dict[str, GmNode]) -> dict:
    """Collect all edges for a SKILL node, grouped by edge type and direction."""
    sid = skill_node.id
    skill_name = skill_node.name

    incoming = {"USED_SKILL": [], "SOLVED_BY": []}
    outgoing = {"REQUIRES": [], "PATCHES": [], "CONFLICTS_WITH": []}
    undirected = {"CONFLICTS_WITH": []}

    # Edges pointing TO this skill (from_id -> skill)
    for e in edges_to(db, sid):
        other = node_cache.get(e.from_id) or find_by_id(db, e.from_id)
        if other is None:
            continue
        node_cache[other.id] = other

        entry = {
            "from_node": other,
            "instruction": e.instruction,
            "condition": e.condition,
            "session_id": e.session_id,
            "created_at": e.created_at,
        }

        if e.type == "USED_SKILL":
            incoming["USED_SKILL"].append(entry)
        elif e.type == "SOLVED_BY":
            incoming["SOLVED_BY"].append(entry)
        elif e.type == "REQUIRES":
            outgoing.setdefault("REQUIRES", []).append(entry)
        elif e.type == "PATCHES":
            outgoing.setdefault("PATCHES", []).append(entry)
        elif e.type == "CONFLICTS_WITH":
            undirected["CONFLICTS_WITH"].append(entry)

    # Edges going FROM this skill (skill -> to_id)
    for e in edges_from(db, sid):
        other = node_cache.get(e.to_id) or find_by_id(db, e.to_id)
        if other is None:
            continue
        node_cache[other.id] = other

        entry = {
            "to_node": other,
            "instruction": e.instruction,
            "condition": e.condition,
            "session_id": e.session_id,
            "created_at": e.created_at,
        }

        if e.type == "REQUIRES":
            outgoing["REQUIRES"].append(entry)
        elif e.type == "PATCHES":
            outgoing["PATCHES"].append(entry)
        elif e.type == "CONFLICTS_WITH":
            undirected["CONFLICTS_WITH"].append(entry)
        elif e.type in ("USED_SKILL", "SOLVED_BY"):
            incoming.setdefault(e.type, []).append({**entry, "from_node": skill_node, "to_node": other})

    # Sort entries within each group by created_at descending
    for group in [incoming, outgoing, undirected]:
        for key in group:
            group[key].sort(key=lambda x: x.get("created_at", 0), reverse=True)

    return {"incoming": incoming, "outgoing": outgoing, "undirected": undirected}


# --- Markdown generation ------------------------------------------------------
def format_edge_section(entries: list[dict], header: str, skill_name: str) -> str:
    """Format a group of edges into a markdown section."""
    if not entries:
        return ""

    lines = [f"### {header}", ""]
    for entry in entries:
        if "from_node" in entry and "to_node" in entry:
            ann = edge_direction_annotation(
                header.upper().replace(" ", "_"),
                entry["from_node"].name,
                entry["to_node"].name,
            )
            lines.append(f"- **{ann}**")
        elif "from_node" in entry:
            other = entry["from_node"]
            ann = edge_direction_annotation("USED_SKILL", other.name, skill_name)
            lines.append(f"- **{ann}**")
        elif "to_node" in entry:
            other = entry["to_node"]
            lines.append(f"- **→ {other.type}:{other.name}**")

        if entry.get("instruction"):
            lines.append(f"  - Instruction: {entry['instruction']}")
        if entry.get("condition"):
            lines.append(f"  - Condition: {entry['condition']}")
        lines.append("")

    return "\n".join(lines)


def generate_skill_md(skill_node: GmNode, edges: dict) -> str:
    """Generate SKILL.md content for a skill node."""
    skill_name = normalize_name(skill_node.name)
    description = skill_node.description or f"Auto-inferred skill: {skill_node.name}"
    content = skill_node.content or ""

    lines = []
    # Frontmatter
    lines.append("---")
    lines.append(f"name: {skill_name}")
    lines.append(f"description: {description}")
    lines.append("---")
    lines.append("")

    # Title
    lines.append(f"# {skill_node.name}")
    lines.append("")

    # Knowledge
    if content:
        lines.append("## Knowledge")
        lines.append("")
        lines.append(content)
        lines.append("")

    # Metadata
    lines.append("## Metadata")
    lines.append("")
    lines.append(f"- **Type**: {skill_node.type}")
    lines.append(f"- **Validated Count**: {skill_node.validated_count}")
    lines.append(f"- **PageRank**: {skill_node.pagerank:.4f}")
    if skill_node.community_id:
        lines.append(f"- **Community**: {skill_node.community_id}")
    lines.append(f"- **Created**: {skill_node.created_at}")
    lines.append(f"- **Updated**: {skill_node.updated_at}")
    if skill_node.source_sessions:
        lines.append(f"- **Source Sessions**: {len(skill_node.source_sessions)}")
    lines.append("")

    # Routing & Relationships
    has_routing = any(v for group in edges.values() for v in group.values())
    if has_routing:
        lines.append("## Routing & Relationships")
        lines.append("")

        incoming = edges.get("incoming", {})
        us = incoming.get("USED_SKILL", [])
        sb = incoming.get("SOLVED_BY", [])

        if us:
            lines.append(format_edge_section(us, "Used By Tasks", skill_node.name))
        if sb:
            lines.append(format_edge_section(sb, "Solves Events", skill_node.name))

        outgoing = edges.get("outgoing", {})
        for key, entries in outgoing.items():
            if entries:
                header = EDGE_LABELS.get(key, key)
                lines.append(format_edge_section(entries, header, skill_node.name))

        undirected = edges.get("undirected", {})
        for key, entries in undirected.items():
            if entries:
                header = EDGE_LABELS.get(key, key)
                lines.append(format_edge_section(entries, header, skill_node.name))

    return "\n".join(lines)


# --- Main --------------------------------------------------------------------
def main():
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Check SRC_DIR / store / skill_memory / skill_memory.db")
        return

    db = get_db()

    # Fetch all SKILL nodes
    rows = db.execute("SELECT * FROM gm_nodes WHERE type='SKILL'").fetchall()
    skill_nodes = [GmNode(dict(row)) for row in rows]

    if not skill_nodes:
        print("No SKILL nodes found in the database.")
        return

    # Pre-populate node cache with ALL nodes
    all_rows = db.execute("SELECT * FROM gm_nodes").fetchall()
    node_cache: dict[str, GmNode] = {row["id"]: GmNode(dict(row)) for row in all_rows}

    # Ensure output directory exists
    PROJECTION_DIR.mkdir(parents=True, exist_ok=True)

    exported = 0
    skipped = 0
    for sn in skill_nodes:
        edges = collect_edges(db, sn, node_cache)
        md_content = generate_skill_md(sn, edges)

        skill_dir_name = normalize_name(sn.name)
        if not skill_dir_name:
            print(f"  SKIP: node '{sn.name}' normalizes to empty name")
            skipped += 1
            continue

        skill_dir = PROJECTION_DIR / skill_dir_name
        skill_dir.mkdir(parents=True, exist_ok=True)

        output_path = skill_dir / "SKILL.md"
        output_path.write_text(md_content, encoding="utf-8")
        print(f"  EXPORTED: {output_path}")
        exported += 1

    total = len(skill_nodes)
    print(f"\nDone. {exported} exported, {skipped} skipped, {total} total SKILL nodes.")
    print(f"Output directory: {PROJECTION_DIR}/")


if __name__ == "__main__":
    main()
