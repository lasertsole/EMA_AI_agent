import os
import json
import requests
import argparse
from pathlib import Path
from config import ROOT_DIR
from dotenv import load_dotenv

current_dir = Path(__file__).parent.resolve()
load_dotenv(ROOT_DIR, override = True)

parser = argparse.ArgumentParser()
parser.add_argument("-a", "--age", type=int, help="你的年龄")
parser.add_argument("--verbose", action="store_true", help="是否输出详细信息")
args = parser.parse_args()


if __name__ == '__main__':
    url = "https://api.modelarts-maas.com/v1/images/generations"  # API地址
    api_key = os.getenv("VL_API_KEY")

    # Send request.
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    data = {
        "model": "qwen-image",  # model参数
        "prompt": "A running cat.",  # 支持中英文
        "size": "1024x1024",
        "response_format": "b64_json",  # 返回格式，可取值为[url, b64_json], 暂仅支持 b64_json，
        "seed": 1  # 取值范围在[0, 2147483648]， 随机种子，默认1
    }
    response = requests.post(url, headers=headers, data=json.dumps(data), verify=False)

    # Print result.
    print(response.status_code)
    print(response.text)