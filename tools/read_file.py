"""Read file tool with project root restriction."""

from __future__ import annotations

from langchain_community.tools.file_management import ReadFileTool

from config import ROOT_DIR


def build_read_file_tool() -> ReadFileTool:
    tool = ReadFileTool(root_dir=str(ROOT_DIR))
    tool.name = "read_file"
    return tool

