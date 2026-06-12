---
name: image_to_text
description: 根据图片路径解析图片，获取图片的描述，从而让非多模态llm拥有视觉能力。
---

**解析普通图片：**
```python
from skills.core.image_to_text.scripts import itt

if __name__ == '__main__':
    user_text: str = "{placeholder}" # <-替换成输入图片的本地绝对路径
    image_path: str = "{placeholder}" # <-输入用户提出的有关图片的问题

    itt(image_path=image_path, user_text = user_text)
```
