---
name: get_weather
description: 查询某个城市的当前天气（温度、湿度、天气描述），通过 python_repl 工具动态执行。
---

# 天气查询技能

当用户询问某个城市的天气时，使用 `python_repl` 工具运行以下 Python 代码来获取天气信息。

将 `CITY` 变量替换为用户指定的城市名（支持中文或英文城市名）。

```python
import requests

CITY = "北京"  # ← 替换为用户指定的城市名

try:
    # 使用 wttr.in 的 JSON API，关闭 SSL 验证以兼容网络环境
    url = f"https://wttr.in/{requests.utils.quote(CITY)}?format=j1"
    resp = requests.get(url, timeout=15, verify=False)
    resp.raise_for_status()
    data = resp.json()

    current = data["current_condition"][0]
    temp_c = current["temp_C"]
    feels_like = current["FeelsLikeC"]
    humidity = current["humidity"]
    desc = current["weatherDesc"][0]["value"]
    wind_kmph = current["windspeedKmph"]
    area = data["nearest_area"][0]["areaName"][0]["value"]
    country = data["nearest_area"][0]["country"][0]["value"]

    print(f"📍 {area}, {country}")
    print(f"🌤 天气: {desc}")
    print(f"🌡 温度: {temp_c}°C（体感 {feels_like}°C）")
    print(f"💧 湿度: {humidity}%")
    print(f"💨 风速: {wind_kmph} km/h")

except requests.exceptions.SSLError:
    # SSL 失败时降级到 HTTP
    try:
        url = f"http://wttr.in/{requests.utils.quote(CITY)}?format=%25C+%25t+%25h+%25w"
        resp = requests.get(url, timeout=15)
        print(f"{CITY} 天气：{resp.text.strip()}")
    except Exception as e:
        print(f"天气服务不可用: {e}")
except Exception as e:
    print(f"查询失败: {e}")
```

**注意事项：**
- 城市名支持中文（如"上海"）或英文（如"Shanghai"）
- 如果 wttr.in 完全不可用，告知用户当前网络环境无法访问天气服务