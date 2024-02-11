"""
Contains configuration / secret keys for the bot to function
"""

import os
from typechecking import ensure_exist

TEST_MODE = False
LOG_CHAT = False

DEFAULT_PREFIX = ">>"

SERVER_DATABASE       = "database/serverdb.json"
USERPLAYLIST_DATABASE = "database/playlistdb.json"

OPUS_LIB = "./libopus.0.dylib"
LOG_FILE = None #"./log.txt"

LOGGER_WEBHOOK_URL = ensure_exist(os.getenv("WEBHOOK_LOGGER_URL"))
ERROR_WEBHOOK_URL  = ensure_exist(os.getenv("ERROR_LOGGER_URL"))

OWNER_ID = 812808602997620756
TEST_SERVER_ID = 915104477521014834

BOT_TOKEN = ensure_exist(os.getenv("TEST_TOKEN" if TEST_MODE else "TOKEN"))
