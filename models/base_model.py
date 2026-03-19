import os
from typing import Any
from pathlib import Path
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.runnables import ConfigurableField

# 获取当前所在文件夹
current_dir = Path(__file__).parent.resolve()

# 加载环境变量
env_path = current_dir / '../.env'
env_path = env_path.resolve()
load_dotenv(env_path, override = True)
api_key = os.getenv("CHAT_API_KEY")
api_name = os.getenv("CHAT_API_NAME")
model_provider = os.getenv("CHAT_MODEL_PROVIDER")

model_config:dict[str, Any] = {
    "model_provider": model_provider,
    "model": api_name,
    "api_key": api_key,
    "temperature": 0,
    "max_retries": 2
}
model_config = {k: v for k, v in model_config.items() if v is not None and v != ""}
base_model = init_chat_model(**model_config) #生成模型对象
base_model = base_model.configurable_fields(
    temperature=ConfigurableField(
        id="temperature",
    )
)