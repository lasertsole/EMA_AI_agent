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