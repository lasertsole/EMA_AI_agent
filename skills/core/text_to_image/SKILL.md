---
name: text_to_image
description: 当用户需要根据文字描述生成图片时，使用 python_repl工具生成图片。
---

```python
import sys
from pathlib import Path
from skills.core.text_to_image.scripts import generate_image

if __name__ == '__main__':
    # 测试用：直接传入prompt
    result = generate_image("测试图片")
    print(f"生成结果: {result}")
```
