import sys
import json
from typing import Any
from pathlib import Path
# 添加项目根目录到 Python 搜索路径
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from models import simple_chat_model


_EVALUATE_SYSTEM_PROMPT = (
    "You are a notification gate for a background agent. "
    "You will be given the original task and the agent's response. "
    "Call the evaluate_notification tool to decide whether the user "
    "should be notified.\n\n"
    "Notify when the response contains actionable information, errors, "
    "completed deliverables, or anything the user explicitly asked to "
    "be reminded about.\n\n"
    "Suppress when the response is a routine status check with nothing "
    "new, a confirmation that everything is normal, or essentially empty."
)

_EVALUATE_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "evaluate_notification",
            "description": "Decide whether the user should be notified about this background task result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "should_notify": {
                        "type": "boolean",
                        "description": "true = result contains actionable/important info the user should see; false = routine or empty, safe to suppress",
                    },
                    "reason": {
                        "type": "string",
                        "description": "One-sentence reason for the decision",
                    },
                },
                "required": ["should_notify"],
            },
        },
    }
]

def main(response: str, task_context: str):
    llm_response = simple_chat_model.bind_tools(_EVALUATE_TOOL).invoke([
        {"role": "system", "content": _EVALUATE_SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"## Original task\n{task_context}\n\n"
            f"## Agent response\n{response}"
        )},
    ])
    print("llm_response:", llm_response)

if __name__ == "__main__":
    main("解决了", "打印 123")