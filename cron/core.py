from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Shanghai"))