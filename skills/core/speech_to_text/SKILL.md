---
name: speech_to_text
description: When the user needs to transcribe speech into text, use the python_repl tool to generate text.
---

```python
import sys
from pathlib import Path
from skills.core.speech_to_text.scripts import stt

if __name__ == '__main__':
    audio_path: str = "{placeholder}"  # <- replace with the absolute path of the input audio file
    stt(audio_path)
```