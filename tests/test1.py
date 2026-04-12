import sys
from pathlib import Path

# 添加项目根目录到 Python 搜索路径
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from context_engine.agent_memory import retrieve_history_prompt, retrieve_history_by_last_n_prompt, delete_old_history_by_n_days_ago


from context_engine import add_history

if __name__ == "__main__":
    add_history(session_id= "1", user_text = "我帮你吧，你站不起来吧，先休息一下", ai_text = "好的，我先休息一下")
    print(retrieve_history_prompt(user_text = "休息没", session_id = "1"))
    print(retrieve_history_by_last_n_prompt(session_id = "1"))
    delete_old_history_by_n_days_ago(n_days_ago = 0)