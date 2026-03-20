import time
import random
import string

def uid(p: str) -> str:
    timestamp = int(time.time() * 1000)
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))

    return f"{p}-{timestamp}-{random_str}"