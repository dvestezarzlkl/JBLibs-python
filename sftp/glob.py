import re

VERSION:str = "3.6.0"

BASE_DIR = "/home_sftp_users"
SAFE_NAME_RGX = re.compile(r'^[a-zA-Z0-9._-]+$')
