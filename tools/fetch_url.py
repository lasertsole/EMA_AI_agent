"""Fetch URL tool with HTML cleanup."""

from __future__ import annotations

import requests
import urllib3
from langchain_community.tools import RequestsGetTool
from langchain_community.utilities.requests import RequestsWrapper
from bs4 import BeautifulSoup

# Suppress SSL warnings when verify=False is used
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class CleanFetchTool(RequestsGetTool):
    name: str = "fetch_url"
    description: str = "Fetch a URL and return cleaned text content."

    def _run(self, url: str) -> str:
        try:
            # Use requests directly with SSL verification disabled and a timeout
            session = requests.Session()
            session.verify = False
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            return f"Error fetching {url}: {e}"

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n")
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return "\n".join(lines[:2000])


def build_fetch_tool() -> CleanFetchTool:
    tool = CleanFetchTool(
        requests_wrapper=RequestsWrapper(),
        allow_dangerous_requests=True,
    )
    tool.handle_tool_error = True
    return tool
