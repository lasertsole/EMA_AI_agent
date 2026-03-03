"""Python REPL tool."""

from __future__ import annotations

from langchain_experimental.tools import PythonREPLTool


def build_python_repl_tool() -> PythonREPLTool:
    tool = PythonREPLTool()
    tool.name = "python_repl"
    return tool

