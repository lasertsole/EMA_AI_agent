from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse

@wrap_model_call
async def wrap_model_call(request: ModelRequest, handler) -> ModelResponse:
    """
    根据对话复杂度动态选择 DeepSeek 模型:
    - 复杂：deepseek-reasoner
    - 简单：deepseek-chat
    """
    # messages = request.state.get("messages", [])
    # print(messages)

    # 结果异步返回
    for attempt in range(3):
        try:
            res = await handler(request)
            print(res)
            return res
        except Exception:
            if attempt == 2:
                raise