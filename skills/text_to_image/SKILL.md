---
name: text_to_image
description: 当用户需要根据文字描述生成图片时，使用 python_repl工具生成图片。
---

```python
import sys
from pathlib import Path

# 动态添加项目根目录到 sys.path
current_file = Path(__file__).resolve()
project_root: Path = current_file.parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import os
import json
import base64
import requests
import argparse
from dotenv import load_dotenv
from config.path import SRC_DIR
from pub_func import generate_tsid

# 加载环境变量
load_dotenv(project_root / ".env", override=True)

text: str = "{placeholder}" # <-替换成用户要生成图像的文字描述

if __name__ == '__main__':
    try:
        url = "https://api.modelarts-maas.com/v1/images/generations"  # API地址
        api_key = os.getenv("VL_API_KEY")
        
        if not api_key:
            print("错误: 未找到VL_API_KEY环境变量")
            sys.stdout.flush()
            sys.exit(1)

        # Send request.
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        data = {
            "model": "qwen-image",  # model参数
            "prompt": text,  # 支持中英文
            "size": "1024x1024",
            "response_format": "b64_json",  # 返回格式，可取值为[url, b64_json], 暂仅支持 b64_json，
            "seed": 1  # 取值范围在[0, 2147483648]， 随机种子，默认1
        }
        
        print(f"正在调用API生成图片...")
        sys.stdout.flush()
        response = requests.post(url, headers=headers, data=json.dumps(data), verify=False)

        save_path = Path(SRC_DIR) / "temp" / f"{generate_tsid()}.png"

        # 确保目录存在
        save_path.parent.mkdir(parents=True, exist_ok=True)

        status_code = response.status_code
        if status_code == 200:
            # 解析响应数据
            response_data = response.json()
            if 'data' in response_data and len(response_data['data']) > 0:
                b64_data = response_data['data'][0]['b64_json']
                
                # 修复：处理Data URL格式
                if b64_data.startswith('data:'):
                    # 提取真正的base64部分
                    # data:image/png;base64,iVBORw0KGgoAAA...
                    parts = b64_data.split(',', 1)
                    if len(parts) == 2:
                        b64_data = parts[1]
                        print(f"已提取纯base64数据，长度: {len(b64_data)}")
                        sys.stdout.flush()
                    else:
                        print(f"警告: 无法解析Data URL格式: {b64_data[:50]}...")
                        sys.stdout.flush()
                
                # 解码base64
                try:
                    image_data = base64.b64decode(b64_data)
                    
                    # 保存图片
                    with open(save_path, "wb") as f:
                        f.write(image_data)

                    print(f"图片保存成功，保存路径为：{save_path}")
                    sys.stdout.flush()
                    print(f"文件大小: {save_path.stat().st_size} 字节")
                    sys.stdout.flush()
                    
                except Exception as decode_error:
                    print(f"base64解码失败: {decode_error}")
                    sys.stdout.flush()
                    print(f"base64数据长度: {len(b64_data)}")
                    sys.stdout.flush()
                    
            else:
                print(f"API响应格式错误: {response_data}")
                sys.stdout.flush()
        else:
            print(f"请求失败，状态码：{status_code}")
            sys.stdout.flush()
            print(f"响应内容: {response.text}")
            sys.stdout.flush()

    except Exception as e:
        print(f"发生错误：{e}")
        sys.stdout.flush()
        import traceback

```