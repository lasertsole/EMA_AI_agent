"""Session Manager -JSON file-based conversation persistence with metadata."""

import json
import time
from pathlib import Path
from typing import Any


class SessionManager:
    """Manages conversation history as JSON files in session/ directory.

    Storage format (v2):
    {
        "title": "会话标题",
        "created_at": 1706000000,
        "updated_at": 1706000000,
        "messages": [{"role": "user", "content": "..."}, ...]
    }
    """

    def __init__(self) -> None:
        self._session_dir: Path | None = None

    def initialize(self, base_dir: Path) -> None:
        self._session_dir = base_dir / "session"
        self._session_dir.mkdir(exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        assert self._session_dir is not None
        safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
        return self._session_dir / f"{safe_id}.json"

    def _read_file(self, session_id: str) -> dict[str, Any]:
        """Read session file and normalize to v2 format."""
        path = self._session_path(session_id)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # Migrate v1 (plain list) to v2 (object with metadata)
            if isinstance(data, list):
                now = time.time()
                return {
                    "title": session_id,
                    "create_at": path.stat().st_ctime,
                    "updated_at": now,
                    "messages": data,
                }
            return data
        except (json.JSONDecodeError, Exception):
            return {}

    def _write_file(self, session_id: str, data: dict[str, Any]) -> None:
        """Write session data to file."""
        data["updated_at"] = time.time()
        path = self._session_path(session_id)
        path.write_text(
            json.dumps(data, ensure_ascii= False, indent=2),
            encoding="utf-8"
        )

    def create_session(self, session_id: str) -> dict[str, Any]:
        """Create a new empty session. Returns metadata."""
        now = time.time()
        data: dict[str, Any] = {
            "title": "New Chat",
            "created_at": now,
            "updated_at": now,
            "messages": []
        }
        self._write_file(session_id, data)
        return {"id": session_id, "title": data["title"], "created_at":now, "updated_at": now}

    def load_session(self, session_id: str) -> list[dict[str, Any]]:
        """Load a conversation history for a session."""
        data = self._read_file(session_id)
        if not data:
            return []
        return data.get("messages", [])

    def save_message(
            self,
            session_id: str,
            role: str,
            content: str,
            tool_calls: list[dict[str, Any]] | None= None
    ) -> None:
        """Append a message to the session history."""
        data = self._read_file(session_id)
        if not data:
            now = time.time()
            data = {
                "title": "New Chat",
                "created_at": now,
                "updated_at": now,
                "messages": []
            }
        msg: dict[str, Any] = {"role": role,"content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        data["messages"].append(msg)
        self._write_file(session_id, data)

    def rename_session(self, session_id: str, title: str) -> None:
        """Rename a session."""
        data = self._read_file(session_id)
        if not data:
            return
        data["title"] = title
        self._write_file(session_id, data)

    def update_session(self, session_id: str, title: str) -> None:
        """Update session title (alias for rename_session)."""
        self.rename_session(session_id, title)

    def delete_session(self, session_id: str) -> None:
        """Delete a session file."""
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()

    def get_raw_messages(self, session_id: str) -> dict[str, Any]:
        """Return the complete session data including all messages."""
        data = self._read_file(session_id)
        if not data:
            return {"title": "", "messages": []}
        return data

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions with metadata."""
        assert self._session_dir is not None
        session: list[dict[str, Any]] = []
        for f in sorted(self._session_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse= True):
            try:
                raw = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    title = raw.get("title", f.stem)
                    updated_at = raw.get("updated_at", f.stat().st_mtime)
                else:
                    title = f.stem
                    updated_at = f.stat().st_mtime
            except Exception:
                title = f.stem
                updated_at = f.stat().st_mtime

            session.append({
                "id": f.stem,
                "title": title,
                "updated_at": updated_at
            })
        return session

    def compress_history(
            self, session_id: str, summary: str, num_to_remove: int
    ) -> None:
        """Archive first N messages and store summary as compressed_context."""
        assert self._session_dir is not None
        data = self._read_file(session_id)
        if not data:
            return

        messages = data.get("messages", [])
        archived_messages = messages[:num_to_remove]

        # Archive to sessions/archived/
        archived_dir = self._session_dir / "archived"
        archived_dir.mkdir(exist_ok=True)
        archived_data = {
            "session_id": session_id,
            "archived_at": time.time(),
            "messages": archived_messages,
        }
        archived_path = archived_dir / f"{session_id}_{int(time.time())}.json"
        archived_path.write_text(
            json.dumps(archived_data, ensure_ascii= False, indent=2),
            encoding="utf-8"
        )

        # Remove archived messages from session
        data["messages"] = messages[num_to_remove:]

        # Append summary to compressed_context (support multiple compressions)
        existing_context = data.get("compressed_context", "")
        if existing_context:
            data["compressed_context"] = f"{existing_context}\n---\n{summary}"
        else:
            data["compressed_context"] = summary

        self._write_file(session_id, data)

    def get_compressed_context(self, session_id: str) -> str | None:
        """Return compressed context if any."""
        data = self._read_file(session_id)
        if not data:
            return ""
        return data.get("compressed_context")

    def load_session_for_agent(self, session_id: str) -> list[dict[str, Any]]:
        """Load session history merged for LLM context.

        Since we now save multiple consecutive assistant messages per turn,
        this method combines them back into single assistant messages to
        maintain proper user/assistant alternation for the LLM.

        If compressed_context exists, inserts it at the head as an assistant
        message so the LLM retains prior context.
        """
        data = self._read_file(session_id)
        messages = data.get("messages", []) if data else []

        merged: list[dict[str, Any]] = []

        # Inject compressed context as the first message if available
        compressed = data.get("compressed_context", "") if data else ""
        if compressed:
            merged.append({
                "role": "assistant",
                "content": f"[以下是之前对话的摘要]\n{compressed}"
            })

        for msg in messages:
            if (
                    merged
                    and merged[-1]["role"] == "assistant"
                    and msg["role"] == "assistant"
            ):
                # Combine consecutive assistant messages
                merged[-1]["content"] += "\n" + msg["content"]
            else:
                # Strip tool_calls for agent context (not needed by LLM)
                merged.append({"role": msg["role"], "content": msg["content"]})
        return merged

    def get_message_count(self, session_id: str) -> int:
        """Return the number of messages in a session."""
        data = self._read_file(session_id)
        if not data:
            return 0
        return len(data.get("messages", []))


session_manager = SessionManager()