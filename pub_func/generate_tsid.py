from datetime import datetime

def generate_tsid()->str:
    """
    生成时间戳 ID: YYYYMMDDHHmmss（如 202602260705）
    同时作为可读时间和唯一标识
    """
    now = datetime.now()
    year = now.year
    month = str(now.month).zfill(2)
    day = str(now.day).zfill(2)
    hour = str(now.hour).zfill(2)
    minute = str(now.minute).zfill(2)
    second = str(now.second).zfill(2)

    return f"{year}{month}{day}{hour}{minute}{second}"