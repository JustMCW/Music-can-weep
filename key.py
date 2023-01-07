"""
Contains keys for the bot to function
"""

import os
import re
import sys
import pathlib

DEFAULT_PREFIX = ">>"

ENTRY_DIR = pathlib.Path(sys.argv[0]).parent.absolute()
RUN_PATH = str(pathlib.Path(__file__).parent.relative_to(ENTRY_DIR)) + "/"

SERVER_DATABASE    = RUN_PATH + "Database/serverdb.json"
USERPLAYLIST_DATABASE = RUN_PATH + "Database/playlistdb.json"

OPUS_LIB = RUN_PATH + "libopus.0.dylib"
LOG_FILE = RUN_PATH + "./log.txt"

LOGGER_WEBHOOK_URL = "https://discord.com/api/webhooks/1060053650128519298/o7ZR2wVjVpOc9Rk8zBDAPsO6ZHJQp_s8epS-yWJS5v_ANb7IDu6cZ9nesVnqEQyd-xlZ"
ERROR_WEBHOOK_URL  = "https://discord.com/api/webhooks/960588563026677840/5NVR3WZaFvbMaZTajbkIaxFrQcBjcFjArU7Zp3Ifd_vMolPlGbvphAelrHwajw07UuOg"

OWNER_ID : int = 812808602997620756
TEST_SERVER_ID = 915104477521014834

def _extract_bot_token() -> str:
    #Getting out token through various of ways

    try:
        BOT_TOKEN = os.environ.get("TOKEN")
        if not BOT_TOKEN:
            BOT_TOKEN = sys.argv[1] #passing of an argument
    except IndexError: #mcw test bot
        with open("../.tokens.txt","r") as TKF:
            BOT_TOKEN = dict(re.findall("(.*) = (.*)",TKF.read() )) ["Music-can-weep-beta"]
    else: #mcw bot
        if BOT_TOKEN.lower() == "mcw":
            with open("../.tokens.txt","r") as TKF:
                BOT_TOKEN = dict(re.findall("(.*) = (.*)",TKF.read() )) ["Music-can-weep"]
    
    return BOT_TOKEN