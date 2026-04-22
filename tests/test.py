

from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage

from agent import built_agent
from logging import Logger, getLogger
from pub_func import get_agent_configurable

logger: Logger = getLogger(__name__)

agent = built_agent(temperature=0.5)

res = agent.invoke(input={"messages": [HumanMessage(content="你好")]}, config=get_agent_configurable("1"))
print(res)