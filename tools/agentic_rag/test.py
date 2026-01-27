import asyncio
from native import _query_background_info
from query_transformations import build_query_by_re_writen_graph

async def main():
    query_by_re_writen_graph = build_query_by_re_writen_graph(retrieve_call=_query_background_info)
    print(await query_by_re_writen_graph.ainvoke({"input": "樱羽艾玛。"}))

if __name__ == "__main__":
    asyncio.run(main())