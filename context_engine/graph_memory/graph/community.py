"""
graph_memory - Community Detection

社区检测 — Label Propagation Algorithm

原理：每个节点初始自成一个社区，迭代中每个节点采纳邻居中最频繁的社区标签。
      收敛后自然形成社区划分。

为什么选 Label Propagation 而不是 Louvain：
  - 实现简单（50 行核心逻辑）
  - 不需要外部库
  - 对小图（< 10000 节点）效果够好
  - O(iterations * edges)，几千节点 < 5ms

用途：
  - 发现知识域（Docker 相关技能自动聚成一组）
  - recall 时可以拉整个社区的节点
  - assemble 时同社区节点放一起，上下文更连贯
  - kg_stats 展示社区分布
"""

import re
import os
import random
import sqlite3
from sqlite3 import Connection
from langchain_core.messages import AIMessage
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from typing import Callable, Awaitable, Optional, TypedDict, List, Any
from ..store.core import update_communities, upsert_community_summary, prune_community_summaries


class CommunityResult(TypedDict):
    """社区检测结果"""
    labels: dict[str, str]
    communities: dict[str, list[str]]
    count: int


def detect_communities(db: Connection, max_iter: int = 50) -> CommunityResult:
    """
    运行 Label Propagation 并写回 gm_nodes.community_id

    把有向边当无向边处理（知识关联不分方向）

    Args:
        db: SQLite 数据库连接
        max_iter: 最大迭代次数

    Returns:
        包含标签、社区和数量的结果字典
    """
    # 读取活跃节点
    cursor = db.cursor()
    cursor.execute("SELECT id FROM gm_nodes WHERE status='active'")
    node_rows = cursor.fetchall()

    if not node_rows:
        return {"labels": {}, "communities": {}, "count": 0}

    node_ids = [row[0] for row in node_rows]

    # 读取边，构建无向邻接表
    cursor.execute("SELECT from_id, to_id FROM gm_edges")
    edge_rows = cursor.fetchall()

    node_set = set(node_ids)
    adj: dict[str, list[str]] = {node_id: [] for node_id in node_ids}

    for from_id, to_id in edge_rows:
        if from_id not in node_set or to_id not in node_set:
            continue
        adj[from_id].append(to_id)
        adj[to_id].append(from_id)

    # 初始标签：每个节点 = 自己的 ID
    label: dict[str, str] = {node_id: node_id for node_id in node_ids}

    # 迭代
    for _ in range(max_iter):
        changed = False

        # 随机打乱遍历顺序（减少震荡）
        shuffled = node_ids.copy()
        random.shuffle(shuffled)

        for node_id in shuffled:
            neighbors = adj.get(node_id, [])
            if not neighbors:
                continue

            # 统计邻居标签频次
            freq: dict[str, int] = {}
            for nb in neighbors:
                neighbor_label = label.get(nb, node_id)
                freq[neighbor_label] = freq.get(neighbor_label, 0) + 1

            # 取频次最高的标签（相同频次取字典序最小，保证确定性）
            best_label = label.get(node_id, node_id)
            best_count = 0

            for lbl, count in sorted(freq.items()):
                if count > best_count or (count == best_count and lbl < best_label):
                    best_label = lbl
                    best_count = count

            if label.get(node_id) != best_label:
                label[node_id] = best_label
                changed = True

        if not changed:
            break

    # 构建社区映射
    communities: dict[str, list[str]] = {}
    for node_id, community_id in label.items():
        if community_id not in communities:
            communities[community_id] = []
        communities[community_id].append(node_id)

    # 给社区编号（用最大成员数排序，编号 c-1, c-2, ...）
    sorted_communities = sorted(
        communities.items(),
        key=lambda x: len(x[1]),
        reverse=True
    )

    rename_map = {old_id: f"c-{i + 1}" for i, (old_id, _) in enumerate(sorted_communities)}

    # 重命名标签
    final_labels = {
        node_id: rename_map.get(old_label, old_label)
        for node_id, old_label in label.items()
    }

    final_communities = {
        rename_map.get(old_id, old_id): members
        for old_id, members in communities.items()
    }

    # 写回数据库
    update_communities(db, final_labels)

    return {
        "labels": final_labels,
        "communities": final_communities,
        "count": len(final_communities),
    }


def get_community_peers(
    db: Connection,
    node_id: str,
    limit: int = 5
) -> list[str]:
    """
    获取同社区的节点 ID 列表

    recall 时用：找到种子节点 → 拉同社区的其他节点作为补充

    Args:
        db: SQLite 数据库连接
        node_id: 种子节点 ID
        limit: 返回的最大节点数

    Returns:
        同社区的节点 ID 列表
    """
    cursor = db.cursor()
    cursor.execute(
        "SELECT community_id FROM gm_nodes WHERE id=? AND status='active'",
        (node_id,)
    )
    row = cursor.fetchone()

    if not row or not row[0]:
        return []

    community_id = row[0]

    cursor.execute("""
        SELECT id FROM gm_nodes
        WHERE community_id=? AND id!=? AND status='active'
        ORDER BY validated_count DESC, updated_at DESC
        LIMIT ?
    """, (community_id, node_id, limit))

    return [r[0] for r in cursor.fetchall()]


# ─── 社区描述生成 ────────────────────────────────────────────

# 类型定义
CompleteFn = Callable[[str, str], Awaitable[str]]
EmbedFn = Callable[[str], Awaitable[list[float]]]

COMMUNITY_SUMMARY_SYS = """你是知识图谱摘要引擎。根据节点列表，用简短的描述概括这组节点的主题领域。
要求：
- 只返回短语本身，不要解释
- 描述涵盖的工具/技术/任务领域
- 不要使用"社区"这个词"""


async def summarize_communities(
    db: Connection,
    communities: dict[str, list[str]],
    llm: BaseChatModel,
    embed: Optional[Embeddings] = None,
) -> int:
    """
    为所有社区生成 LLM 摘要描述 + embedding 向量

    调用时机：runMaintenance → detectCommunities 之后

    Args:
        db: SQLite 数据库连接
        communities: 社区 ID 到成员节点 ID 列表的映射
        llm: LLM 补全函数
        embed: Embedding

    Returns:
        生成的摘要数量
    """
    prune_community_summaries(db)
    generated: int = 0

    cursor: sqlite3.Cursor = db.cursor()

    for community_id, member_ids in communities.items():
        if not member_ids:
            continue

        placeholders: str = ",".join("?" * len(member_ids))
        db.row_factory = sqlite3.Row
        cursor.execute(f"""
            SELECT name, type, description FROM gm_nodes
            WHERE id IN ({placeholders}) AND status='active'
            ORDER BY validated_count DESC
            LIMIT 10
        """, (*member_ids,))

        members: List[Any] = [dict(c) for c in cursor.fetchall()]

        if not members:
            continue

        member_text:str = "\n".join(
            f"{m_type}:{name} — {desc}"
            for name, m_type, desc in members
        )

        try:
            # LLM 生成描述
            summary: AIMessage = await llm.ainvoke(
                COMMUNITY_SUMMARY_SYS+f"社区成员：\n{member_text}",
            )

            # 清理输出
            cleaned: str = summary.content.strip()
            cleaned: str = re.sub(r'<think>[\s\S]*?</think>', '', cleaned, flags=re.IGNORECASE)
            cleaned: str = re.sub(r'<think>[\s\S]*', '', cleaned, flags=re.IGNORECASE)
            cleaned: str = re.sub(r'^["\'「"]|["\'「""]$', '', cleaned)
            cleaned: str = cleaned.replace('\n', ' ')
            cleaned: str = re.sub(r'\s{2,}', ' ', cleaned)
            cleaned: str = cleaned.strip()[:100]

            if not cleaned:
                continue

            # 生成社区 embedding（用描述 + 成员名拼接）
            embedding: Optional[list[float]] = None
            if embed:
                try:
                    embed_text = f"{cleaned}\n{', '.join([m[0] for m in members])}"
                    embedding: List[float] = await embed.aembed_query(embed_text)
                except Exception:
                    if os.environ.get('GM_DEBUG'):
                        print(f"  [DEBUG] community embedding failed for {community_id}")

            upsert_community_summary(db, community_id, cleaned, len(member_ids), embedding)
            generated += 1

        except Exception as err:
            print(f"  [WARN] community summary failed for {community_id}: {err}")

    return generated
