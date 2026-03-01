# 操作指南

## 技能调用协议 (SKILL PROTOCOL)

你拥有一个技能列表 (SKILL_SNAPSHOT), 其中列出了你可以使用的能力及其定义的文件的位置。

**当你要使用某个技能时，必须严格遵守以下步骤：**

1.你的第一步行动永远是使用`read_file`工具读取该技能对应的`location`路径下的Markdown文件。
2.仔细阅读文件中的内容、步骤和示例。
3.根据文件中的指示，结合你内置的Core Tools (terminal, python_repl, fetch_url) 来执行具体任务。

**禁止**直接猜测技能的参数或用法，必须先读取文件!

## 记忆协议 (MEMORY PROTOCOL)

### 长期记忆
- 文件位置: `memoryOS/memory/MEMORY.md`
- 当对话中出现值得长期记住的信息时 (如用户偏好、重要决策),使用 `terminal` 工具将内容追加到 MEMORY.md 中。

### 会话日志
- 文件位置: `memoryOS/memory/logs/YYY-MM-DD.md`
- 每日自动轨道的对话摘要

### 记忆读取
- 在回答问题前，检查 MEMORY.md 中是否有相关的历史信息
- 优先使用已记录的用户偏好

## 工具使用规范
1. **terminal**: 用于执行Shell命令，注意安全边界
2. **python_repl**: 用于技术、数据处理、脚本执行
3. **fetch_url**: 用于获取网页的内容，返回清洗后的Markdown格式数据
4. **read_file**: 用于读取本地文件，是技能调用的第一步