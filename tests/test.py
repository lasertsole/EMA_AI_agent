from config import SUBAGENT_TEMPLATE_DIR
from pub_func import render_template_file

subagent_announce_path = (SUBAGENT_TEMPLATE_DIR / "subagent_announce.md").resolve().as_posix()
print(render_template_file(file_path=subagent_announce_path, variables={"label": 1, "status_text": 2, "task": 3, "result": 4}))