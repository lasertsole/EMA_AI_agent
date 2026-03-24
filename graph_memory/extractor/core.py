"""
graph-memory — 知识图谱提取引擎
"""

import re
import os
import json
from ..type import GmConfig
from langchain_core.messages import SystemMessage, HumanMessage

from models import chat_model
from typing import TypedDict, List, Dict, Set, Optional, Any, Literal

from langgraph.graph.state import CompiledStateGraph

# ─── 节点/边合法值 ──────────────────────────────────────────────

VALID_NODE_TYPES = {"TASK", "SKILL", "EVENT"}
VALID_EDGE_TYPES = {"USED_SKILL", "SOLVED_BY", "REQUIRES", "PATCHES", "CONFLICTS_WITH"}

# 边类型 → 合法的 from 节点类型
EDGE_FROM_CONSTRAINT: Dict[str, Set[str]] = {
    "USED_SKILL": {"TASK"},
    "SOLVED_BY": {"EVENT", "SKILL"},
    "REQUIRES": {"SKILL"},
    "PATCHES": {"SKILL"},
    "CONFLICTS_WITH": {"SKILL"},
}

# 边类型 → 合法的 to 节点类型
EDGE_TO_CONSTRAINT: Dict[str, Set[str]] = {
    "USED_SKILL": {"SKILL"},
    "SOLVED_BY": {"SKILL"},
    "REQUIRES": {"SKILL"},
    "PATCHES": {"SKILL"},
    "CONFLICTS_WITH": {"SKILL"},
}


# ─── 类型定义 ─────────────────────────────────────────────────

class Node(TypedDict):
    """节点"""
    type: Literal["TASK", "SKILL", "EVENT"]
    name: str
    description: str
    content: str


class Edge(TypedDict):
    """边"""
    from_node: str
    to_node: str
    type: str
    instruction: str
    condition: Optional[str]


class ExtractionResult(TypedDict):
    """提取结果"""
    nodes: List[Node]
    edges: List[Edge]


class PromotedSkill(Node):
    """升级的技能"""
    type: Literal["SKILL"]


class FinalizeResult(TypedDict):
    """整理结果"""
    promoted_skills: List[PromotedSkill]
    new_edges: List[Edge]
    invalidations: List[str]


# ─── 提取 System Prompt ─────────────────────────────────────────

EXTRACT_SYS = """你是 graph-memory 知识图谱提取引擎，从 AI Agent 对话中提取可复用的结构化知识三元组（节点 + 关系）。
提取的知识将在未来对话中被召回，帮助 Agent 避免重复犯错、复用已验证方案。
输出严格 JSON：{"nodes":[...],"edges":[...]}，不包含任何额外文字。

1. 节点提取：
   1.1 从对话中识别三类知识节点：
       - TASK：用户要求 Agent 完成的具体任务，或对话中讨论、分析、对比的主题
       - SKILL：可复用的操作技能，有具体工具/命令/API，有明确触发条件，步骤可直接执行
       - EVENT：一次性的报错或异常，记录现象、原因和解决方法
   1.2 每个节点必须包含 4 个字段，缺一不可：
       - type：节点类型，只允许 TASK / SKILL / EVENT
       - name：全小写连字符命名，确保整个提取过程命名一致
       - description：一句话说明什么场景触发
       - content：纯文本格式的知识内容（见 1.4 的模板）
   1.3 name 命名规范：
       - TASK：动词 - 对象格式，如 deploy-bilibili-mcp、extract-pdf-tables、compare-ocr-engines
       - SKILL：工具 - 操作格式，如 conda-env-create、docker-port-expose
       - EVENT：现象 - 工具格式，如 importerror-libgl1、timeout-paddleocr
       - 已有节点列表会提供，相同事物必须复用已有 name，不得创建重复节点
   1.4 content 模板（纯文本，按 type 选用）：
       TASK → "[name]\n目标：...\n执行步骤:\n1. ...\n2. ...\n结果：..."
       SKILL → "[name]\n触发条件：...\n执行步骤:\n1. ...\n2. ...\n常见错误:\n- ... -> ..."
       EVENT → "[name]\n现象：...\n原因：...\n解决方法：..."

2. 关系提取：
   2.1 识别节点之间直接、明确的关系，只允许以下 5 种边类型。
   2.2 每条边必须包含 from、to、type、instruction 四个字段，缺一不可。
   2.3 边类型定义与方向约束（严格遵守，不得混用）：

       USED_SKILL
         方向：TASK → SKILL（且仅限此方向）
         含义：任务执行过程中使用了该技能
         instruction：写第几步用的、怎么调用的、传了什么参数
         判定：from 节点是 TASK，to 节点是 SKILL

       SOLVED_BY
         方向：EVENT → SKILL 或 SKILL → SKILL
         含义：该报错/问题被该技能解决
         instruction：写具体执行了什么命令/操作来解决
         condition（必填）：写什么错误或条件触发了这个解决方案
         判定：from 节点是 EVENT 或 SKILL，to 节点是 SKILL
         注意：TASK 节点不能作为 SOLVED_BY 的 from，TASK 使用技能必须用 USED_SKILL

       REQUIRES
         方向：SKILL → SKILL
         含义：执行该技能前必须先完成另一个技能
         instruction：写为什么依赖、怎么判断前置条件是否已满足

       PATCHES
         方向：SKILL → SKILL（新 → 旧）
         含义：新技能修正/替代了旧技能的做法
         instruction：写旧方案有什么问题、新方案改了什么

       CONFLICTS_WITH
         方向：SKILL ↔ SKILL（双向）
         含义：两个技能在同一场景互斥
         instruction：写冲突的具体表现、应该选哪个

   2.4 关系方向选择决策树（按此顺序判定）：
       a. from 是 TASK，to 是 SKILL → 必须用 USED_SKILL
       b. from 是 EVENT，to 是 SKILL → 必须用 SOLVED_BY
       c. from 和 to 都是 SKILL → 根据语义选 SOLVED_BY / REQUIRES / PATCHES / CONFLICTS_WITH
       d. 不存在其他合法组合，不符合以上任何一条的关系不要提取

3. 提取策略（宁多勿漏）：
   3.1 所有对话内容都应尝试提取，包括讨论、分析、对比、方案选型等
   3.2 用户纠正 AI 的错误时，旧做法和新做法都要提取，用 PATCHES 边关联
   3.3 讨论和对比类对话提取为 TASK，记录讨论的结论和要点
   3.4 只有纯粹的寒暄问候（如"你好""谢谢"）才不提取

4. 输出规范：
   4.1 只返回 JSON，格式为 {"nodes":[...],"edges":[...]}
   4.2 禁止 markdown 代码块包裹，禁止解释文字，禁止额外字段
   4.3 没有知识产出时返回 {"nodes":[],"edges":[]}
   4.4 每条 edge 的 instruction 必须写具体可执行的内容，不能为空或写"见上文"

示例 1（TASK + SKILL + USED_SKILL 边）：

对话摘要：用户要求抓取 B 站弹幕，Agent 使用 bili-tool 的 danmaku 子命令完成。

输出：
{"nodes":[{"type":"TASK","name":"extract-bilibili-danmaku","description":"从 B 站视频中批量抓取弹幕数据","content":"extract-bilibili-danmaku\n目标：从指定 B 站视频抓取全部弹幕\n执行步骤:\n1. 获取视频 BV 号\n2. 调用 bili-tool danmaku --bv BVxxx\n3. 输出 JSON 格式弹幕列表\n结果：成功抓取 2341 条弹幕"},{"type":"SKILL","name":"bili-tool-danmaku","description":"使用 bili-tool 抓取 B 站视频弹幕","content":"bili-tool-danmaku\n触发条件：需要抓取 B 站视频弹幕时\n执行步骤:\n1. pip install bilibili-api-python\n2. python bili_tool.py danmaku --bv BVxxx --output danmaku.json\n常见错误:\n- cookie 过期 -> 重新获取 SESSDATA"}],"edges":[{"from":"extract-bilibili-danmaku","to":"bili-tool-danmaku","type":"USED_SKILL","instruction":"第 2 步调用 bili-tool danmaku 子命令，传入 --bv 和 --output 参数"}]}

示例 2（EVENT + SKILL + SOLVED_BY 边）：

对话摘要：执行 PaddleOCR 时报 libGL 缺失，通过 apt 安装解决。

输出：
{"nodes":[{"type":"EVENT","name":"importerror-libgl1","description":"导入 cv2/paddleocr 时报 libGL.so.1 缺失","content":"importerror-libgl1\n现象：ImportError: libGL.so.1: cannot open shared object file\n原因：OpenCV 依赖系统级 libGL 库，conda/pip 不自动安装\n解决方法：apt install -y libgl1-mesa-glx"},{"type":"SKILL","name":"apt-install-libgl1","description":"安装 libgl1 解决 OpenCV 系统依赖缺失","content":"apt-install-libgl1\n触发条件：ImportError: libGL.so.1\n执行步骤:\n1. sudo apt update\n2. sudo apt install -y libgl1-mesa-glx\n常见错误:\n- Permission denied -> 加 sudo"}],"edges":[{"from":"importerror-libgl1","to":"apt-install-libgl1","type":"SOLVED_BY","instruction":"执行 sudo apt install -y libgl1-mesa-glx","condition":"报 ImportError: libGL.so.1 时"}]}"""


# ─── 提取 User Prompt ───────────────────────────────────────────

def extract_user_prompt(msgs: str, existing: str) -> str:
    """构建提取的 user prompt"""
    return f"""<Existing Nodes>
{existing or "（无）"}

<Conversation>
{msgs}"""


# ─── 整理 System Prompt ─────────────────────────────────────────

FINALIZE_SYS = """你是图谱节点整理引擎，对本次对话产生的节点做 session 结束前的最终审查。
审查本次对话所有节点，执行以下三项操作，输出严格 JSON。

1. EVENT 升级为 SKILL：
   如果某个 EVENT 节点具有通用复用价值（不限于特定场景），将其升级为 SKILL。
   升级时需要：改名为 SKILL 命名规范（工具 - 操作）、完善 content 为 SKILL 纯文本模板格式。
   写入 promotedSkills 数组。

2. 补充遗漏关系：
   整体回顾所有节点，发现单次提取时难以察觉的跨节点关系。
   关系类型只允许：USED_SKILL、SOLVED_BY、REQUIRES、PATCHES、CONFLICTS_WITH。
   严格遵守方向约束：TASK->SKILL 用 USED_SKILL，EVENT->SKILL 用 SOLVED_BY。
   写入 newEdges 数组。

3. 标记失效节点：
   因本次对话中的新发现而失效的旧节点，将其 node_id 写入 invalidations 数组。

没有需要处理的项返回空数组。只返回 JSON，禁止额外文字。
格式：{"promotedSkills":[{"type":"SKILL","name":"...","description":"...","content":"..."}],"newEdges":[{"from":"...","to":"...","type":"...","instruction":"..."}],"invalidations":["node-id"]}"""


# ─── 整理 User Prompt ───────────────────────────────────────────

def finalize_user_prompt(nodes: List[Dict], summary: str) -> str:
    """构建整理的 user prompt"""
    nodes_summary = json.dumps([
        {
            'id': n['id'],
            'type': n['type'],
            'name': n['name'],
            'description': n['description'],
            'v': n.get('validatedCount', 0)
        }
        for n in nodes
    ], indent=2, ensure_ascii=False)

    return f"""<Session Nodes>
{nodes_summary}

<Graph Summary>
{summary}"""


# ─── 名称标准化 ────────────────────────────────────────────────

def normalize_name(name: str) -> str:
    """
    标准化名称：全小写，空格转连字符，保留中文

    Args:
        name: 原始名称

    Returns:
        标准化后的名称
    """
    name = name.strip().lower()
    name = re.sub(r'[\s_]+', '-', name)
    name = re.sub(r'[^a-z0-9\u4e00-\u9fff\-]', '', name)
    name = re.sub(r'-{2,}', '-', name)
    name = name.strip('-')

    return name


# ─── 边类型自动修正 ─────────────────────────────────────────────
def correct_edge_type(
        edge: Dict[str, Any],
        name_to_type: Dict[str, str],
) -> Optional[Dict[str, Any]]:
    """
    根据节点类型自动修正边类型

    Args:
        edge: 边数据
        name_to_type: 名称到类型的映射

    Returns:
        修正后的边，如果不合法则返回 None
    """
    from_name = normalize_name(edge.get('from', ''))
    to_name = normalize_name(edge.get('to', ''))

    from_type = name_to_type.get(from_name)
    to_type = name_to_type.get(to_name)

    if not from_type or not to_type:
        return edge

    edge_type = edge.get('type', '')

    # 自动修正边类型
    if from_type == "TASK" and to_type == "SKILL" and edge_type != "USED_SKILL":
        if os.environ.get('GM_DEBUG'):
            print(f"  [DEBUG] edge corrected: {edge['from']} ->[{edge_type}]-> {edge['to']} => USED_SKILL")
        edge_type = "USED_SKILL"

    if from_type == "EVENT" and to_type == "SKILL" and edge_type != "SOLVED_BY":
        if os.environ.get('GM_DEBUG'):
            print(f"  [DEBUG] edge corrected: {edge['from']} ->[{edge_type}]-> {edge['to']} => SOLVED_BY")
        edge_type = "SOLVED_BY"

    # 检查边类型是否合法
    if edge_type not in VALID_EDGE_TYPES:
        if os.environ.get('GM_DEBUG'):
            print(f"  [DEBUG] edge dropped: invalid type '{edge_type}'")
        return None

    # 检查方向约束
    from_ok = from_type in EDGE_FROM_CONSTRAINT.get(edge_type, set())
    to_ok = to_type in EDGE_TO_CONSTRAINT.get(edge_type, set())

    if not from_ok or not to_ok:
        if os.environ.get('GM_DEBUG'):
            print(f"  [DEBUG] edge dropped: {from_type}->[{edge_type}]->{to_type} violates direction constraint")
        return None

    result = edge.copy()
    result['type'] = edge_type
    return result


# ─── JSON 提取 ────────────────────────────────────────────────
def extract_json(raw: str) -> str:
    """
    从 LLM 响应中提取 JSON

    Args:
        raw: 原始响应文本

    Returns:
        提取的 JSON 字符串
    """
    s = raw.strip()

    # 移除 think 标签
    s = re.sub(r'<think>[\s\S]*?</think>', '', s, flags=re.IGNORECASE)
    s = re.sub(r'<think>[\s\S]*', '', s, flags=re.IGNORECASE)

    # 移除 markdown 代码块
    s = re.sub(r'^(?:json)?\s*\n?', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\n?\s*\s*$', '', s)

    s = s.strip()

    # 如果已经是完整的 JSON 对象或数组，直接返回
    if (s.startswith('{') and s.endswith('}')) or (s.startswith('[') and s.endswith(']')):
        return s

    # 尝试提取第一个完整的 JSON 对象
    first = s.find('{')
    last = s.rfind('}')

    if first != -1 and last > first:
        return s[first:last + 1]

    return s

# ─── Extractor ────────────────────────────────────────────────
class Extractor:
    """知识图谱提取器"""

    def __init__(self, cfg: GmConfig):
        """
        初始化提取器

        Args:
            cfg: Graph Memory 配置
            llm: LLM 补全函数
        """
        self._cfg = cfg
        self.llm = cfg.llm

    async def extract(self, messages: List[Dict], existing_names: List[str]) -> ExtractionResult:
        """
        从对话中提取知识图谱

        Args:
            messages: 对话消息列表
            existing_names: 已有节点名称列表

        Returns:
            包含节点和边的提取结果
        """
        # 格式化消息
        msgs_parts = []
        for m in messages:
            role = m.get('role', '?').upper()
            turn_index = m.get('turn_index', 0)
            content = m.get('content', '')

            if isinstance(content, str):
                text = content
            else:
                text = json.dumps(content, ensure_ascii=False)

            msg_text = f"[{role} t={turn_index}]\n{text[:800]}"
            msgs_parts.append(msg_text)

        msgs = "\n\n---\n\n".join(msgs_parts)

        # 调用 LLM
        raw = chat_model.invoke([SystemMessage(EXTRACT_SYS), HumanMessage(extract_user_prompt(msgs, ", ".join(existing_names)))])

        if os.environ.get('GM_DEBUG'):
            print("\n  [DEBUG] LLM raw response (first 2000 chars):")
            print("  " + raw[:2000].replace('\n', '\n  '))

        return self._parse_extract(raw)

    async def finalize(self, session_nodes: List[Dict], graph_summary: str) -> FinalizeResult:
        """
        Session 结束前的最终审查

        Args:
            session_nodes: Session 中的节点列表
            graph_summary: 图谱摘要

        Returns:
            包含升级技能、新边和失效节点的结果
        """
        raw = chat_model.invoke([SystemMessage(FINALIZE_SYS), HumanMessage(finalize_user_prompt(session_nodes, graph_summary))])

        return self._parse_finalize(raw, session_nodes)

    def _parse_extract(self, raw: str) -> ExtractionResult:
        """解析提取结果"""
        try:
            json_str = extract_json(raw)
            p = json.loads(json_str)

            # 过滤和验证节点
            nodes_data = p.get('nodes', [])
            nodes = []

            for n in nodes_data:
                if not n.get('name') or not n.get('type') or not n.get('content'):
                    continue

                if n.get('type') not in VALID_NODE_TYPES:
                    if os.environ.get('GM_DEBUG'):
                        print(f"  [DEBUG] node dropped: invalid type '{n.get('type')}'")
                    continue

                if not n.get('description'):
                    n['description'] = ""

                n['name'] = normalize_name(n['name'])
                nodes.append(n)

            # 构建名称到类型的映射
            name_to_type = {n['name']: n['type'] for n in nodes}

            # 处理和验证边
            edges_data = p.get('edges', [])
            edges = []

            for e in edges_data:
                if not all([e.get('from'), e.get('to'), e.get('type'), e.get('instruction')]):
                    continue

                e['from'] = normalize_name(e['from'])
                e['to'] = normalize_name(e['to'])

                corrected = correct_edge_type(e, name_to_type)
                if corrected:
                    edges.append(corrected)

            return {'nodes': nodes, 'edges': edges}

        except Exception as err:
            if os.environ.get('GM_DEBUG'):
                print(f"  [DEBUG] JSON parse failed: {err}")
                print(f"  [DEBUG] raw content: {raw[:500]}")
            return {'nodes': [], 'edges': []}

    def _parse_finalize(self, raw: str, session_nodes: List[Dict]) -> FinalizeResult:
        """解析整理结果"""
        try:
            json_str = extract_json(raw)
            p = json.loads(json_str)

            # 构建名称到类型的映射
            name_to_type = {}
            for n in session_nodes:
                if n.get('name') and n.get('type'):
                    name_to_type[normalize_name(n['name'])] = n['type']

            # 处理升级的技能
            promoted_skills = [
                n for n in p.get('promotedSkills', [])
                if n.get('name') and n.get('content')
            ]

            for n in promoted_skills:
                name_to_type[normalize_name(n['name'])] = n.get('type', 'SKILL')

            # 处理新边
            new_edges = []
            for e in p.get('newEdges', []):
                if not all([e.get('from'), e.get('to'), e.get('type')]):
                    continue

                if e.get('type') not in VALID_EDGE_TYPES:
                    continue

                e['from'] = normalize_name(e['from'])
                e['to'] = normalize_name(e['to'])

                corrected = correct_edge_type(e, name_to_type)
                if corrected:
                    new_edges.append(corrected)

            return {
                'promoted_skills': promoted_skills,
                'new_edges': new_edges,
                'invalidations': p.get('invalidations', []),
            }

        except Exception:
            return {
                'promoted_skills': [],
                'new_edges': [],
                'invalidations': [],
            }
