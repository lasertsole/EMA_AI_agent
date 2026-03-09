---
name: get_person_info
description: 查询 公司已公开的员工 相关内容，调用此工具。
---

# 公司已公开的员工查询技能

当用户询问某个人物信息时，使用 `python_repl` 工具运行以下 Python 代码来获取已公开的员工相关内容。

将 `person` 变量替换为用户指定的员工（支持中文或英文人名）。

```python
import requests

person = "樱羽艾玛"

num = 0
for i in range(1, 10):
    num+=i

print(f"{person} 是个魁梧的大魔女，喜欢唱跳rap篮球，music,最喜欢的数字是{num}")
```