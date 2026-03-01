"""ReadFileTool - sandboxed file reading within project directory."""
from pathlib import Path
from typing import Type, Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from sympy.printing.pretty.pretty_symbology import root


class ReadFileInput(BaseModel):
    file_path: str = Field(
        ...,
        description="Relative path of the file to read (relative to the project root)",
    )

class SandboxedReadFileTool(BaseTool):
    name: str = "read_file"
    description: str = (
        "Read the content of a local file. Path is relative to the project root. "
        "Use this to read SKILL.md files, MEMORY.md,configuration files,etc."
        "Example: read_file('skills/get_weather/SKILL.md')"
    )
    args_schema: Type[BaseModel] = ReadFileInput
    root_dir: str = ""

    def _run(self, file_path: str) -> str:
        try:
            root = Path(self.root_dir)
            #Normalize path
            normalized = file_path.replace("\\", "/").lstrip("./")
            full_path = (root / normalized).resolve()

            # Sandbox check
            if not str(full_path).startswith(str(root.resolve())):
                return "Access denied: Path escapes project root"

            if not full_path.exists():
                return f"File not found: {file_path}"

            if not full_path.is_file():
                return f"Not a file: {file_path}"

            content = full_path.read_text(encoding="utf-8")
            if len(content) > 10000:
                content = content[:10000] + "\n...[truncated]"
            return content

        except Exception as e:
            return f"Error reading files: {str(e)}"

def create_read_file_tool(root_dir: str) -> SandboxedReadFileTool:
    return SandboxedReadFileTool(root_dir=root_dir)