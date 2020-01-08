import random
import string


class Config:
    SECRET_KEY = ''.join(random.choice(string.ascii_lowercase) for _ in range(30))
    DEBUG = False
