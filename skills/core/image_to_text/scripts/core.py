import sys
from pathlib import Path

# 动态添加项目根目录到 sys.path
current_file = Path(__file__).resolve()
project_root: Path = current_file.parents[4]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import base64
import tempfile
import requests
from PIL import Image
from models import vl_model
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from pub_func.validator import is_url

# 加载环境变量
load_dotenv(project_root / ".env", override=True)


def itt(image_path: str, user_text: str = "请尽可能详细的描述图片中的内容。")-> None:
    """识别图片内容（支持本地文件路径或 URL）

    Args:
        image_path: 本地图片路径或图片 URL
        user_text: 对图片的描述要求，默认为"请尽可能详细的描述图片中的内容。"
    """
    # ----- 阶段1：获取图片数据 -----
    if is_url(image_path):
        # URL → 下载到临时文件
        print(f"正在从 URL 下载图片: {image_path}")
        try:
            resp = requests.get(image_path, stream=True, timeout=60)
            resp.raise_for_status()
            # 从 Content-Type 推断后缀
            content_type = resp.headers.get("Content-Type", "")
            suffix = ".png"
            if "jpeg" in content_type or "jpg" in content_type:
                suffix = ".jpg"
            elif "webp" in content_type:
                suffix = ".webp"
            elif "gif" in content_type:
                suffix = ".gif"

            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(resp.content)
                tmp_path = Path(tmp.name)

            print(f"图片已下载到临时文件: {tmp_path}")
            path = tmp_path
        except Exception as e:
            print(f"[错误] 下载图片失败: {e}")
            return None
    else:
        path = Path(image_path)
        try:
            if not path.exists():
                print(f"文件不存在: {image_path}")
                return None
        except Exception:
            print(f"文件路径无效: {image_path}")
            return None

    # ----- 阶段2：验证图片完整性 -----
    try:
        with Image.open(path) as img:
            img.verify()
    except Exception:
        print(f"该文件不是有效图片: {image_path}")
        if is_url(image_path):
            tmp_path.unlink(missing_ok=True)
        return None

    # ----- 阶段3：转换为 base64 -----
    try:
        with Image.open(path) as img:
            img_format = img.format.lower()  # jpg, png, webp 等

        with open(path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"[错误] 图片转换失败: {e}")
        if is_url(image_path):
            tmp_path.unlink(missing_ok=True)
        return None

    # ----- 阶段4：调用视觉模型 -----
    try:
        image_base64: str = f"data:image/{img_format};base64,{encoded_string}"
        content_list: list[dict[str, str]] = [
            {"type": "text", "text": user_text},
            {"type": "image_url", "image_url": {"url": image_base64}},
        ]

        res = vl_model.invoke([HumanMessage(content=content_list)])

        print("图片识别完成，内容为:\n", res.content)
        return None
    except Exception as e:
        print(f"[错误] 视觉模型调用失败: {e}")
    finally:
        # 如果是从 URL 下载的临时文件，清理掉
        if is_url(image_path):
            tmp_path.unlink(missing_ok=True)