import os
import json
import requests
from dotenv import load_dotenv

# 加载环境变量和模型初始化（同上）
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../.env')
load_dotenv(env_path, override=True)
api_key = os.getenv("BGE_M3")

# Send request.
url = "https://api.modelarts-maas.com/v1/rerank"
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {api_key}'
}
data = {
    "model": "bge-reranker-v2-m3",
    "query": "牛是一种动物如何冲泡一杯好喝的咖啡？",  # input类型可为string或string[]。
    "documents": [
        "咖啡豆的产地主要分布在赤道附近，被称为‘咖啡带’。",
        "法压壶的步骤：1. 研磨咖啡豆。2. 加入热水。3. 压下压杆。4. 倒入杯中。",
        "意式浓缩咖啡需要一台高压机器，在9个大气压下快速萃取。",
        "挑选咖啡豆时，要注意其烘焙日期，新鲜的豆子风味更佳。",
        "手冲咖啡的技巧：控制水流速度、均匀注水和合适的水温（90-96°C）是关键。"
    ]
}

response = requests.post(url, headers=headers, data=json.dumps(data), verify=False)

# Print result.
print(response.status_code)
print(response.text)