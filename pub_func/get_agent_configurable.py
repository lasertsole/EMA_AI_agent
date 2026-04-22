from langchain_core.runnables import RunnableConfig

def get_agent_configurable(session_id: str) -> RunnableConfig:
    try:
        return {"configurable": {"thread_id": int(session_id)}}
    except ValueError:
        raise Exception("session_id must be an integer")