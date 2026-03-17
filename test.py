import time
import asyncio
import streamlit as st
from typing import List, Any

messages: List[dict[str, Any]] = []
async def main():
    with st.chat_message("assistant", avatar="./src/avatar/assistant.jpg"):
        with st.status("tool calling.", expanded=True) as status:
            completed_tools: List[str] = []
            completed_placeholder = st.empty()
            current_placeholder = st.empty()

            current_tool_name: str = ""
            current_tool_id: str = ""
            for message in messages:
                tool_calls = message["msg"].get("tool_calls", []) if len(message["msg"].get("tool_calls", [])) > 0 else message["msg"].get("tool_call_chunks", [])

                if message["type"] == "AIMessageChunk":
                    if len(tool_calls) > 0 or current_tool_id.strip():
                        if len(tool_calls) > 0:
                          tool_call = tool_calls[0]

                        if tool_call["name"] and tool_call["name"].strip():
                            current_tool_name = tool_call['name']

                        if tool_call["id"] and tool_call["id"].strip():
                            current_tool_id = tool_call['id']

                    current_placeholder.write(f"calling {current_tool_name} ")

                elif message.get("content", None) is not None:
                    status.update(label="calling", state="complete", expanded=False)

                if message["type"] == "ToolMessage":
                    completed:str = f"calling  {current_tool_name} complete"
                    completed_tools.append(completed)
                    completed_placeholder.markdown("\n\n".join(completed_tools))

                    current_tool_name = ""
                    current_tool_id = ""

                    current_placeholder.empty()

                time.sleep(0.2)