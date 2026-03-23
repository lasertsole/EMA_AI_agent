"""Terminal tool with sandbox and blacklist."""

from __future__ import annotations

from langchain_community.tools import ShellTool

from config import ROOT_DIR


BLACKLIST = {"rm -rf /", "mkfs", "shutdown", "reboot"}


class SafeShellTool(ShellTool):
    """
        name: str = "terminal"
        description: str = "Run shell commands in a sandboxed workspace."
    """

    def _run(self, command: str) -> str:
        for bad in BLACKLIST:
            if bad in command:
                return "Blocked: unsafe command."
        return super()._run(command)


def build_terminal_tool() -> SafeShellTool:
    tool = SafeShellTool(root_dir=str(ROOT_DIR))
    tool.handle_tool_error = True
    return tool

