import os
from dotenv import load_dotenv
from langchain_tavily import TavilySearch

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env')
load_dotenv(env_path, override = True)

tavily_api_key = os.getenv("TAVILY_API_KEY")
web_search = TavilySearch(tavily_api_key=tavily_api_key, max_results = 7)