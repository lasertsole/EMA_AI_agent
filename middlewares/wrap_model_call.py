from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse

@wrap_model_call
async def wrap_model_call(request: ModelRequest, handler) -> ModelResponse:
    return await handler(request)