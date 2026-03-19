import json
import requests
from dotenv import load_dotenv, find_dotenv

env_path = find_dotenv()  # 返回找到的 .env 路径
load_dotenv()  # 会自动查找并加载

if __name__ == '__main__':
    url = "https://api.modelarts-maas.com/v1/images/generations"  # API地址
    api_key = "MAAS_API_KEY"  # 把MAAS_API_KEY替换成已获取的API Key

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