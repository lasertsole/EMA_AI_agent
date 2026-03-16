import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

current_dir = Path(__file__).parent.resolve()
env_path = current_dir / '../.env'
env_path = env_path.resolve()
load_dotenv(env_path, override = True)
api_name = os.getenv("LOCAL_CHAT_API_NAME")
model_provider = os.getenv("LOCAL_CHAT_MODEL_PROVIDER")

async def main():
    routing_model = init_chat_model(
        model_provider=model_provider,
        model=api_name,
        temperature=0,
    )
    print(routing_model.invoke("What is the capital of France?"))

if __name__ == "__main__":
    asyncio.run(main())