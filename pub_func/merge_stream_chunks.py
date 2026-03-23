import json
from langchain_core.messages import BaseMessage, AIMessage, ToolMessage, AIMessageChunk


def merge_stream_chunks(msg_chunks:BaseMessage):
    ai_content = ""

    target_message_list: list[BaseMessage] = []
    tool_call_content = ""
    tool_call_id = ""
    tool_call_name = ""
    for m in msg_chunks:
        if isinstance(m, AIMessageChunk):
            if m.get("content", None) is not None:
                ai_content += m.get("content", "")
            elif len(m.get("tool_call_chunks", [])) > 0:
                for chunk in m["tool_call_chunks"]:
                    if chunk["type"] == "tool_call_chunk":
                        tool_call_content += chunk.get("args", "")

                        if chunk.get("id", None) is not None:
                            tool_call_id = chunk["id"]
                        if chunk.get("name", None) is not None:
                            tool_call_name = chunk["name"]

            elif tool_call_content != "":
                target_message_list.append(AIMessage(content = "", tool_calls = [{ "id": tool_call_id, "name": tool_call_name, "args": json.loads(tool_call_content) }] ))
                tool_call_content = ""
                tool_call_id = ""
                tool_call_name = ""
        elif isinstance(m, ToolMessage):
            target_message_list.append(ToolMessage(content = tool_call_content, tool_call_id = tool_call_id, tool_call_name = tool_call_name))