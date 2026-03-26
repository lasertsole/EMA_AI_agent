import json
import math
import asyncio
import logging
from config import SRC_DIR
from . import GmNode
from .type import GmConfig
from .recaller import Recaller
from .extractor import Extractor
from models import simple_chat_model, embed_model
from typing import TypedDict, List, Any, Dict, Callable
from .format import sanitize_tool_use_result_pairing, assemble_context
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from .graph import invalidate_graph_cache, compute_global_page_rank, detect_communities, summarize_communities, run_maintenance
from store import get_db, deprecate, save_message, get_unextracted, get_by_session, upsert_node, find_by_id, find_by_name,\
                   upsert_edge, mark_extracted, edges_from, edges_to

logger = logging.getLogger(__name__)

class SliceLastTurn(TypedDict):
    messages: List[BaseMessage]
    tokens: int
    dropped: int

class RecallResult(TypedDict):
    nodes: List[Any]
    edges: List[Any]

# ── 初始化核心模块 ──────────────────────────────────────
DEFAULT_CONFIG: GmConfig = GmConfig(
    db_path=f"{SRC_DIR}/store/graph-memory.db",
    compact_turn_count = 6,
    recall_max_nodes = 6,
    recall_max_depth = 2,
    fresh_tail_count = 10,
    dedup_threshold = 0.90,
    pagerank_damping = 0.85,
    pagerank_iterations = 20,
    embedding = embed_model,
    llm = simple_chat_model
)

db = get_db()
recaller = Recaller(db, DEFAULT_CONFIG)
extractor = Extractor(DEFAULT_CONFIG)

# ── Session运行时状态 ──────────────────────────────────
msg_seq: Dict[str, int] = {}
recalled: Dict[str, RecallResult] = {}
turnCounter = Dict[str, int] = {} # 社区维护计数器

# ─── 取最后一轮完整用户对话 ─────────────────────────────────
def estimate_msg_tokens(msg: BaseMessage) -> int:
    content = msg.content

    if isinstance(content, str):
        text = content
    else:
        text = json.dumps(content) if content is not None else ""

    return math.ceil(len(text) / 3)

TOKEN_MAX = 6000
def _truncate_msg(msg: BaseMessage)-> BaseMessage:
    if not isinstance(msg, ToolMessage):
        return msg

    content = getattr(msg, "content", "")
    if not isinstance(content, str):
        text:str = json.dumps(content) if content is not None else ""
    else:
        text:str = content

    if len(text) <= TOKEN_MAX:
        return msg

    head_len = int(TOKEN_MAX * 0.6)
    tail_len = int(TOKEN_MAX * 0.3)

    truncated_text = (
        f"{text[:head_len]}\n"
        f"...[truncated {len(text) - head_len - tail_len} chars]...\n"
        f"{text[-tail_len:]}"
    )

    return msg.model_copy(deep=True, update={"content": truncated_text})

def slice_last_turn(messages: List[BaseMessage]) -> SliceLastTurn:
    """
        从最后一个 role=user 到消息末尾，完整保留。
        tool_use/tool_result 天然配对不会切断。
        超长 tool_result 截断（保头尾砍中间）。
    """
    if len(messages)==0:
        return { "messages": [], "tokens": 0, "dropped": 0 }

    last_user_idx = -1

    for i, msg in enumerate(reversed(messages)):
        if isinstance(msg, HumanMessage):
            last_user_idx = len(messages) - 1 - i
            break

    if last_user_idx < 0:
        last_user_idx = 0

    kept = messages[last_user_idx:]
    dropped = last_user_idx


    kept = [_truncate_msg(msg) for msg in kept]

    tokens = 0
    for msg in kept:
        tokens += estimate_msg_tokens(msg)

    return { "messages": kept, "tokens": tokens, "dropped": dropped }

# ─── 规范化消息 content，确保 OpenClaw 对 content.filter() 不崩 ──
def normalize_message_content(messages: list[BaseMessage]) -> list[BaseMessage]:
    """标准化消息内容格式

    - 如果 content 是数组 → 修复畸形的 text block
    - 如果 content 是字符串 → 包装成标准 content block 数组
    - 如果 content 是 None/undefined → 空 text block
    """
    result = []

    for msg in messages:
        c = getattr(msg, "content", None)

        # 如果 content 是数组 → 修复畸形 block
        if isinstance(c, list):
            fixed = []
            changed = False

            for block in c:
                if block and isinstance(block, dict) and block.get("type") == "text":
                    if "text" not in block:
                        # 缺少 text 属性，补充空字符串
                        fixed_block = {**block, "text": ""}
                        fixed.append(fixed_block)
                        changed = True
                        continue

                fixed.append(block)

            # 如果有修改，返回新对象
            if changed:
                if isinstance(msg, dict):
                    new_msg = {**msg, "content": fixed}
                else:
                    new_msg = msg.model_copy(deep=True, update={"content": fixed})
                result.append(new_msg)
            else:
                result.append(msg)
            continue

        # 如果 content 是字符串 → 包装成标准 content block 数组
        if isinstance(c, str):
            if isinstance(msg, dict):
                new_msg = {**msg, "content": [{"type": "text", "text": c}]}
            else:
                new_msg = msg.model_copy(deep=True, update={"content": [{"type": "text", "text": c}]})
            result.append(new_msg)
            continue

        # 如果 content 是 None/null → 空 text block
        if c is None:
            if isinstance(msg, dict):
                new_msg = {**msg, "content": [{"type": "text", "text": ""}]}
            else:
                new_msg = msg.model_copy(deep=True, update={"content": [{"type": "text", "text": ""}]})
            result.append(new_msg)
            continue

        # 其他情况原样返回
        result.append(msg)

    return result


def ingest_message(session_id: str, message: BaseMessage)-> None:
    """ 存一条消息到 gm_messages（同步，零 LLM）"""
    seq = msg_seq.get(session_id)
    if seq is None:
        # 首次入库：从数据库读取当前最大 turn_index，避免重启后 turn_index 重叠
        cursor = db.cursor()
        cursor.execute(
            "SELECT MAX(turn_index) as maxTurn FROM gm_messages WHERE session_id=?",
            (session_id,)
        )
        row = cursor.fetchone()
        seq = row[0] if row and row[0] is not None else 0

    seq += 1
    msg_seq[session_id] = seq

    role = getattr(message, 'type', 'unknown') or 'unknown'
    save_message(db, session_id, seq, role, message)


async def run_turn_extract(session_id: str) -> None:
    """每轮结束后直接提取当前轮的消息"""
    try:
        # 获取未提取的消息（包含刚入库的）
        msgs = get_unextracted(db, session_id, 50)
        if not msgs:
            return

        existing = [node["name"] for node in get_by_session(db, session_id)]
        result = await extractor.extract(messages= msgs, existing_names = existing)

        name_to_id: Dict[str, str] = {}
        for nc in result["nodes"]:
            upsert_result = upsert_node(
                db,
                {
                    "type": nc["type"],
                    "name": nc["name"],
                    "description": nc["description"],
                    "content": nc["content"],
                },
                session_id
            )
            node = upsert_result["node"]
            name_to_id[node["name"]] = node["id"]

            # 异步生成 embedding，不阻塞主流程
            asyncio.create_task(recaller.sync_embed(node))

        for ec in result["edges"]:
            from_id = name_to_id.get(ec["from_node"])
            if from_id is None:
                found = find_by_id(db, ec["from_node"])
                from_id = found["id"] if found else None

            to_id = name_to_id.get(ec["to_node"])
            if to_id is None:
                found = find_by_name(db, ec["to_node"])
                to_id = found["id"] if found else None

            if from_id and to_id:
                upsert_edge(
                    db,
                    {
                        "from_id": from_id,
                        "to_id": to_id,
                        "type": ec["type"],
                        "instruction": ec["instruction"],
                        "condition": ec["condition"],
                        "session_id": session_id,
                    }
                )

        max_turn = max(msg["turn_index"] for msg in msgs)
        mark_extracted(db, session_id, max_turn)

        if result["nodes"] or result["edges"]:
            invalidate_graph_cache()
    except Exception as e:
        logger.error(f"[graph-memory] turn extract failed: {e}")


async def assemble(
        session_id: str,
        messages: list[BaseMessage]
) -> dict:
    active_nodes = get_by_session(db, session_id)
    active_edges = []
    for node in active_nodes:
        active_edges.extend(edges_from(db, node["id"]))
        active_edges.extend(edges_to(db, node["id"]))

    rec = recalled.get(session_id, {"nodes": [], "edges": []})
    total_gm_nodes = len(active_nodes) + len(rec["nodes"])

    if total_gm_nodes == 0:
        return {
            "messages": normalize_message_content(messages),
            "estimated_tokens": 0
        }

    # ── 1. 最后一轮完整对话 ─────────────────────────
    last_turn = slice_last_turn(messages)
    repaired = sanitize_tool_use_result_pairing(last_turn["messages"])

    # ── 2. 图谱 + 溯源 ─────────────────────────────
    assemble_result = assemble_context(
        db,
        {
            "token_budget": 0,
            "active_nodes": active_nodes,
            "active_edges": active_edges,
            "recalled_nodes": rec["nodes"],
            "recalled_edges": rec["edges"],
        }
    )
    xml = assemble_result["xml"]
    system_prompt = assemble_result["system_prompt"]
    gm_tokens = assemble_result["tokens"]
    episodic_xml = assemble_result["episodic_xml"]
    episodic_tokens = assemble_result["episodic_tokens"]

    if last_turn["dropped"] > 0 or episodic_tokens > 0:
        logger.info(
            f"[graph-memory] assemble: last turn {len(last_turn['messages'])} msgs "
            f"(~{last_turn['tokens']} tok), dropped {last_turn['dropped']} older msgs, "
            f"graph ~{gm_tokens} tok"
            + (f", episodic ~{episodic_tokens} tok" if episodic_tokens > 0 else "")
        )

    # ── 3. 组装 systemPrompt ────────────────────────
    system_prompt_addition: str | None = None
    parts = [system_prompt, xml, episodic_xml]
    filtered_parts = [p for p in parts if p]
    if filtered_parts:
        system_prompt_addition = "\n\n".join(filtered_parts)

    result = {
        "messages": normalize_message_content(repaired),
        "estimated_tokens": gm_tokens + last_turn["tokens"],
    }
    if system_prompt_addition:
        result["system_prompt_addition"] = system_prompt_addition

    return result


async def compact(
        session_id: str,
        current_token_count: int | None = None
) -> dict:
    # compact 仍然保留作为兜底，但主要提取在 after_turn 完成
    msgs = get_unextracted(db, session_id, 50)

    if not msgs:
        return {"ok": True, "compacted": False, "reason": "no messages"}

    try:
        existing = [node["name"] for node in get_by_session(db, session_id)]
        result = await extractor.extract(messages=msgs, existing_names=existing)

        name_to_id: Dict[str, str] = {}
        for nc in result["nodes"]:
            upsert_result = upsert_node(
                db,
                {
                    "type": nc["type"],
                    "name": nc["name"],
                    "description": nc["description"],
                    "content": nc["content"],
                },
                session_id
            )
            node = upsert_result["node"]
            name_to_id[node["name"]] = node["id"]

            # 异步生成 embedding，不阻塞主流程
            asyncio.create_task(recaller.sync_embed(node))

        for ec in result["edges"]:
            from_id = name_to_id.get(ec["from_node"])
            if from_id is None:
                found = find_by_name(db, ec["from_node"])
                from_id = found["id"] if found else None

            to_id = name_to_id.get(ec["to_node"])
            if to_id is None:
                found = find_by_name(db, ec["to_node"])
                to_id = found["id"] if found else None

            if from_id and to_id:
                upsert_edge(
                    db,
                    {
                        "from_id": from_id,
                        "to_id": to_id,
                        "type": ec["type"],
                        "instruction": ec["instruction"],
                        "condition": ec["condition"],
                        "session_id": session_id,
                    }
                )

        max_turn = max(msg["turn_index"] for msg in msgs)
        mark_extracted(db, session_id, max_turn)

        return {
            "ok": True,
            "compacted": True,
            "result": {
                "summary": f"extracted {len(result['nodes'])} nodes, "
                           f"{len(result['edges'])} edges",
                "tokens_before": current_token_count if current_token_count else 0,
            },
        }

    except Exception as err:
        logger.error(f"[graph-memory] compact failed: {err}")
        return {"ok": False, "compacted": False, "reason": str(err)}

async def after_turn(
        session_id: str,
        messages: list[BaseMessage],
) -> None:
    """每轮对话后的处理钩子"""

    # 消息入库（同步，零 LLM）
    new_messages = slice_last_turn(messages)

    for message in new_messages:
        ingest_message(session_id, message)

    total_msgs = msg_seq.get(session_id, 0)
    logger.info(
        f"[graph-memory] after_turn sid={session_id[:8]} "
        f"new_msgs={len(new_messages)} total_msgs={total_msgs}"
    )

    # ★ 每轮直接提取（后台任务）
    async def run_extract():
        try:
            await run_turn_extract(session_id)
        except Exception as err:
            logger.error(f"[graph-memory] turn extract failed: {err}")

    asyncio.create_task(run_extract())

    # ★ 社区维护：每 N 轮触发一次（纯计算，<5ms）
    turns = turnCounter.get(session_id, 0) + 1
    turnCounter[session_id] = turns
    maintain_interval = getattr(DEFAULT_CONFIG, 'compact_turn_count', 7)

    if turns % maintain_interval == 0:
        try:
            invalidate_graph_cache()
            pr = compute_global_page_rank(db, DEFAULT_CONFIG)
            comm = detect_communities(db)

            # 提取 top 3 节点名称
            top_names = [n["name"] for n in pr["top_k"][:3]]
            logger.info(
                f"[graph-memory] periodic maintenance (turn {turns}): "
                f"pagerank top={', '.join(top_names)}, "
                f"communities={comm['count']}"
            )

            # 每次社区检测后立即生成摘要（需要 LLM），确保泛化召回可用
            if comm["communities"] and len(comm["communities"]) > 0:
                embed_fn = getattr(recaller, 'embed', None)
                summaries = await summarize_communities(
                    db,
                    comm["communities"],
                    DEFAULT_CONFIG.llm,
                    embed_fn
                )
                logger.info(
                    f"[graph-memory] community summaries refreshed: "
                    f"{summaries} summaries"
                )

        except Exception as err:
            logger.error(f"[graph-memory] periodic maintenance failed: {err}")


async def prepare_subagent_spawn(parent_session_key: str, child_session_key: str) -> Callable[[], None]:
    """准备子代理启动：复制父代理的记忆到子代理"""
    rec = recalled.get(parent_session_key)
    if rec:
        recalled[child_session_key] = rec

    def rollback():
        if child_session_key in recalled:
            del recalled[child_session_key]

    return rollback


async def on_subagent_ended(child_session_key: str) -> None:
    """子代理结束后清理记忆"""
    if child_session_key in recalled:
        del recalled[child_session_key]
    if child_session_key in msg_seq:
        del msg_seq[child_session_key]


async def dispose() -> None:
    """释放所有内存"""
    msg_seq.clear()
    recalled.clear()


async def session_end(event: dict, ctx: dict) -> None:
    """Session 结束时的清理和知识固化操作"""
    # 获取 session ID（兼容多种字段名）
    sid = (
            ctx.get("sessionKey")
            or ctx.get("sessionId")
            or event.get("sessionKey")
            or event.get("sessionId")
    )

    if not sid:
        return

    try:
        # 获取该 session 的所有节点
        nodes: List[GmNode] = get_by_session(db, sid)

        if nodes:
            # 获取全局 Top 20 节点作为图谱摘要
            cursor = db.cursor()
            cursor.execute(
                "SELECT name, type, validated_count, pagerank FROM gm_nodes WHERE status='active' ORDER BY pagerank DESC LIMIT 20"
            )
            top_nodes = cursor.fetchall()

            # 构建摘要字符串
            summary_parts = []
            for n in top_nodes:
                name, node_type, validated_count, pagerank = n
                summary_parts.append(
                    f"{node_type}:{name}(v{validated_count},pr{pagerank:.3f})"
                )
            summary = ", ".join(summary_parts)

            # 调用整理器进行最终审查
            fin = await extractor.finalize(
                session_nodes=nodes,
                graph_summary=summary
            )

            # 处理升级的技能
            for nc in fin.promoted_skills:
                if nc.name and nc.content:
                    upsert_node(
                        db,
                        {
                            "type": "SKILL",
                            "name": nc.name,
                            "description": nc.description or "",
                            "content": nc.content,
                        },
                        sid
                    )

            # 处理新边
            for ec in fin.new_edges:
                from_node = find_by_name(db, ec.from_node)
                to_node = find_by_name(db, ec.to_node)

                if from_node and to_node:
                    upsert_edge(
                        db,
                        {
                            "from_id": from_node["id"],
                            "to_id": to_node["id"],
                            "type": ec.type,
                            "instruction": ec.instruction,
                            "session_id": sid,
                        }
                    )

            # 标记失效节点
            for node_id in fin.invalidations:
                deprecate(db, node_id)

        # 执行图谱维护
        embed_fn = getattr(recaller, "embed", None)
        result = run_maintenance(db, DEFAULT_CONFIG, DEFAULT_CONFIG.llm, embed_fn)

        # 记录维护日志
        top_pr_names = [
            f"{n['name']}({n['score']:.3f})"
            for n in result["pagerank"]["top_k"][:3]
        ]

        logger.info(
            f"[graph-memory] maintenance: {result['duration_ms']}ms, "
            f"dedup={result['dedup']['merged']}, "
            f"communities={result['community']['count']}, "
            f"summaries={result['community_summaries']}, "
            f"top_pr={', '.join(top_pr_names)}"
        )

    except Exception as err:
        logger.error(f"[graph-memory] session_end error: {err}")
    finally:
        # 清理 Session 状态
        msg_seq.pop(sid, None)
        recalled.pop(sid, None)
        turnCounter.pop(sid, None)