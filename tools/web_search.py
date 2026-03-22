import os
from config import ENV_PATH
from dotenv import load_dotenv
from langchain_tavily import TavilySearch

load_dotenv(ENV_PATH, override = True)

tavily_api_key = os.getenv("TAVILY_API_KEY")
web_search_tool = TavilySearch(tavily_api_key=tavily_api_key, max_results = 7)