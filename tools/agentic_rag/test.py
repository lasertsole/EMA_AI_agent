import asyncio
from native import _query_background_info
from rerank import build_rerank_graph
from query_transformations import build_query_by_re_writen_graph

async def main():
    query = "樱羽艾玛。"

    # query_by_re_writen_graph = build_query_by_re_writen_graph(retrieve_call=_query_background_info)
    # rerank_graph = build_rerank_graph(k = 10)
    # answers = await query_by_re_writen_graph.ainvoke({"input": query})
    # answers = answers["output"]
    #
    # answers = await rerank_graph.ainvoke({"input": {"query": query, "answers":answers}})
    # answers = answers["output"]
    # print(answers)

    print(_query_background_info(query))

if __name__ == "__main__":
    asyncio.run(main())