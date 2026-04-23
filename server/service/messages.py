import asyncio
import textwrap
import requests
from asyncio import Task
from robyn import SSEMessage
from config import ASSISTANT_NAME
from type import MultiModalMessage
from models import simple_chat_model
from agent import built_agent, ModelType
from langchain.messages import AIMessageChunk
from langchain_core.prompts import PromptTemplate
from typing import AsyncGenerator, Any, Dict, List
from langgraph.graph.state import CompiledStateGraph
from workspace.prompt_builder import build_system_prompt
from ..DAO import maybe_extract_memory, clear_session as clear_session_DAO
from pub_func import slice_last_turn, sanitize_tool_use_result_pairing, get_agent_configurable
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, ToolCall, ToolCallChunk
from context_engine import after_turn, assemble, rectification_and_standardization, add_history, retrieve_history_prompt, retrieve_history_by_last_n_prompt

def _get_agent_history_list(agent: CompiledStateGraph, session_id: str)-> List[BaseMessage]:
    return agent.get_state(config=get_agent_configurable(session_id)).values.get("messages", [])

def _mixed_query_with_last_n_turns(turns_of_history: str, query: str) -> str:
    """根据前n论对话重写query"""
    system_prompt: str = textwrap.dedent("""
        你是一个问题改写助手,根据用户给的几轮历史上下文,将当前用户的提问内容补充得更加完整。
        要求:
            - 如果query有 她、它、他等第三人称代词,根据上下文 将第三人称代词 成正确的名字
                如:
                <turns>
                    <turn>
                        小雪今天在参加翻跟头比赛。
                        
                        小雪啊,翻跟斗一向拿手。
                    </turn>
                </turns>
                query: '你猜她拿了第几名?' -> '你猜小雪拿了第几名?'

            - 如果query有 指代不明的地方, 根据上下文将query改写成更具体的query
                如:
                    <turns>
                        <turn>
                            iphone17摄像头参数怎么样?
                            
                            4800 万像素融合式主摄:26 毫米焦距,ƒ/1.6 光圈,传感器位移式光学图像防抖功能,100% Focus Pixels,支持超高分辨率照片 (2400 万像素和 4800 万像素)
                            同时支持 1200 万像素光学品质的 2 倍长焦功能:52 毫米焦距,ƒ/1.6 光圈,传感器位移式光学图像防抖功能,100% Focus Pixels。
                        </turn>
                    </turns>
                query: '参数那么高啊,那这个参数跟真正的相机比如何?' -> '4800 万像素融合式主摄, 1200 万像素光学品质的 跟真正的相机比如何?'

            - 其他情况尽量让语句简单整洁的同时包含丰富的有效信息
    """)

    user_prompt_template: str = textwrap.dedent("""
        =================以下是几轮历史上下文=================
        {turns_of_history}

        =================当前需要改写的query=================
        {query}
    """)

    systemPrompt_Template = PromptTemplate(
        template=system_prompt,
        input_variables=[]
    )

    userPrompt_Template = PromptTemplate(
        template=user_prompt_template,
        input_variables=["turns_of_history", "query"]
    )

    from langchain_core.messages import SystemMessage, HumanMessage

    messages = [
        SystemMessage(content=systemPrompt_Template.format()),
        HumanMessage(content=userPrompt_Template.format(
            turns_of_history=turns_of_history,
            query=query
        ))
    ]

    res = simple_chat_model.invoke(messages)
    return res.content if hasattr(res, 'content') else str(res)


"""以下是组装自带上下文的agent逻辑"""
async def _assemble_agent(session_id: str, multi_modal_message: MultiModalMessage) -> CompiledStateGraph:

    # 创建agent
    agent: CompiledStateGraph = built_agent()

    user_text:str = multi_modal_message.text

    # 获取最近几条对话
    recent_messages_addition:str = retrieve_history_by_last_n_prompt(session_id=session_id)

    # 用最近几条对话 和 query， 生成信息特征更丰富的  用户问题 - transformer_user_text
    transformer_user_text:str = _mixed_query_with_last_n_turns(turns_of_history=recent_messages_addition, query=user_text)

    # 获取graph-memory系统提示词
    all_messages: List[BaseMessage] = _get_agent_history_list(agent, session_id)
    assemble_result: Dict[str, str] = await assemble(user_text = transformer_user_text, messages = all_messages)
    graph_system_prompt_addition:str = assemble_result.get("system_prompt_addition", "")

    # 获取agent-memory系统提示词
    agent_system_prompt_addition: str = await retrieve_history_prompt(user_text = transformer_user_text, session_id = session_id)

    # 构建系统提示
    messages: List[BaseMessage] = [
        SystemMessage(
            content=
                build_system_prompt()
                + graph_system_prompt_addition
                + agent_system_prompt_addition
                + recent_messages_addition
        )
    ]

    content_list:List[dict[str, str]] = [{"type": "text", "text": user_text}]
    if multi_modal_message.image_base64_list:
        for image_base64 in multi_modal_message.image_base64_list:
            content_list.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}})
            # 切换模型
            agent = built_agent(model_type = ModelType.VL_MODEL, enable_tool = False)

    messages.append(HumanMessage(content = content_list))

    # 直接将上下文写入checkpointer内
    agent.update_state(config = get_agent_configurable(session_id), values = {"messages": messages})

    return agent

"""以上是组装自带上下文的agent逻辑"""

"""以下是返回信息逻辑"""
_current_tool_name: str = ""
_current_tool_id: str = ""
async def async_generator(session_id: str, multi_modal_message: MultiModalMessage, is_stream: bool = True)-> AsyncGenerator[str, None]:
    global _current_tool_name
    global _current_tool_id

    # 若有用户要求记忆的内容 添加 跨线程记忆中
    user_text: str = multi_modal_message.text
    maybe_extract_memory(user_text)

    # 创建已经组装好上下文的agent
    agent: CompiledStateGraph = await _assemble_agent(session_id, multi_modal_message)
    ai_text:str = ""

    try:
        yield SSEMessage(f"{ASSISTANT_NAME}:")
        
        if is_stream:
            # 用已组装好上下文的agent直接输出
            async for chunk in agent.astream(input=None, config=get_agent_configurable(session_id), stream_mode="messages"):
                msg_chunk: BaseMessage = chunk[0]
                if isinstance(msg_chunk, AIMessageChunk):
                    # 以下是输出工具信息
                    tool_calls: List[ToolCall] | List[ToolCallChunk] = msg_chunk.tool_calls if msg_chunk.tool_calls and len(
                        msg_chunk.tool_calls) > 0 else msg_chunk.tool_call_chunks
                    if len(tool_calls) > 0 or _current_tool_id.strip():
                        repeat_flag: bool = True  # 防止重复输出工具信息
                        if len(tool_calls) > 0:
                            tool_call = tool_calls[0]

                            if tool_call["name"]:
                                if tool_call["name"].strip() or tool_call["name"].strip() != _current_tool_name:
                                    _current_tool_name = tool_call['name']

                            if tool_call["id"]:
                                if tool_call["id"].strip() or tool_call["id"].strip() != _current_tool_id:
                                    _current_tool_id = tool_call['id']
                                    repeat_flag = False

                        if not repeat_flag:
                            res: str = f"\n\n**调用工具 {_current_tool_name} 中**"
                            ai_text += res
                            yield SSEMessage(res)

                    if _current_tool_id and msg_chunk.content is not None and msg_chunk.content:
                        res: str = f"\n\n**调用工具 {_current_tool_name} 结束。**\n\n"
                        ai_text += res
                        yield SSEMessage(res)
                        _current_tool_id = ""
                    # 以上是输出工具信息

                    # 以下是对话信息
                    if len(msg_chunk.content) > 0:
                        res: str = msg_chunk.content
                        ai_text += res
                        yield SSEMessage(res)
                    # 以上是对话信息

        else:
            result: dict[str, Any] = await agent.ainvoke(input = None, config = get_agent_configurable(session_id))
            res: str = result["messages"][-1].content
            ai_text += res
            yield SSEMessage(res)

    except requests.exceptions.HTTPError as e:
        yield SSEMessage(f"请求失败: {e.response.text}")
    except requests.exceptions.Timeout as e:
        yield SSEMessage(f"请求超时: {e.args[0]}")

    except Exception as e:
        raise Exception(e)

    finally:
        # 重置工具信息
        _current_tool_name = ""
        _current_tool_id = ""

        # 获取 格式化后的最后一轮对话的 消息列表
        all_messages: List[BaseMessage] = _get_agent_history_list(agent, session_id)
        last_turn_messages: List[BaseMessage] = slice_last_turn(all_messages)["messages"]
        format_last_turn_messages: List[BaseMessage] = sanitize_tool_use_result_pairing(last_turn_messages)

        # 启动上下文引擎的 后处理
        after_turn_task: Task = asyncio.create_task(after_turn(session_id = session_id, last_turn_messages = format_last_turn_messages))

        # 将用户消息持久化
        add_history_task: Task = asyncio.create_task(add_history(session_id = session_id, user_text=user_text, ai_text=ai_text))

        await asyncio.gather(after_turn_task, add_history_task)


"""以上是返回信息逻辑"""

"""以下是会话结束逻辑"""
async def session_end(session_id: str):
    await rectification_and_standardization(session_id = session_id)
"""以上是会话结束逻辑"""

async def clear_session(session_id: str):
    clear_session_DAO(session_id = session_id)