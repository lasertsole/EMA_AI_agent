"""Terminal tool with sandbox and blacklist."""

from __future__ import annotations

from langchain_community.tools import ShellTool
from typing import Union, List
from config import ROOT_DIR


BLACKLIST = {"rm -rf /", "mkfs", "shutdown", "reboot"}


class SafeShellTool(ShellTool):
    """
        name: str = "terminal"
        description: str = "Run shell commands in a sandboxed workspace."
    """

    def _run(self, commands: Union[str, List[str]], **kwargs) -> str:
        for bad in BLACKLIST:
            if bad in commands:
                return "Blocked: unsafe command."
        return super()._run(commands)


def build_terminal_tool() -> SafeShellTool:
    tool = ShellTool(root_dir = str(ROOT_DIR))
    tool.handle_tool_error = True
    return tool

