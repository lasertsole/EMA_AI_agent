from config import API_HOST, API_PORT
from skills import build_skills_snapshot

if __name__ == "__main__":
    print(f"🚀 服务器启动中... 地址：http://{API_HOST}:{API_PORT}")

    # 服务器启动时重构技能快照，用于保证本次服务器启动中skills提示词稳定，从而保证模型 前缀缓存 稳定
    build_skills_snapshot()

    # 导入以注册所有路由和处理器
    from .trigger import app
    app.start(host=API_HOST, port=API_PORT)