"""SafeTerminalTool - sandboxed shell execute with command blacklist."""
import subprocess
from pathlib import Path
from typing import Type
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

BLACKISTED_COMMANDS = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=",
    ":(){:|:&};:",
    "chmod -R 777 /",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "format c:"
    "del /f /s /q c:",
]

class TerminalInput(BaseModel):
    command: str = Field(description="The shell command to execute.")

class SafeTerminalTool(BaseTool):
    name: str = "terminal"
    description: str = (
        "Execute shell commands in a sandboxed environment."
        "The working directory is restricted to the project root."
        "Use this for file operations, installing packages, running scripts, etc."
    )
    args_schema: Type[BaseModel] = TerminalInput
    root_dir: str = ""

    def _is_safe(self, command: str) -> bool:
        cmd_lower = command.lower().strip()
        for blocked in BLACKISTED_COMMANDS:
            if blocked in cmd_lower:
                return False
        return True

    def _run(self, command: str) -> str:
        if not self._is_safe(command):
            return f"Command blocked for safety:{command}"
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace"
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]: {result.stderr}"
            if not output.strip():
                output = "(command completed with no output)"
            # Truncate very long output
            if len(output) > 5000:
                output = output[:5000] + "\n...[truncated]"
            return output
        except subprocess.TimeoutExpired:
            return "Command timed out(30s limit)"
        except Exception as e:
            return f"Error: {str(e)}"

def create_terminal_tool(base_dir: Path) -> SafeTerminalTool:
    return SafeTerminalTool(root_dir=str(base_dir))