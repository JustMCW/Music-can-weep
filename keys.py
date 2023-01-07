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

SERVER_DATABASE       = "database/serverdb.json"
USERPLAYLIST_DATABASE = "database/playlistdb.json"

OPUS_LIB = "./libopus.0.dylib"
LOG_FILE = "./log.txt"

LOGGER_WEBHOOK_URL = os.environ.get("WEBHOOK_LOGGER_URL")
ERROR_WEBHOOK_URL  = os.environ.get("ERROR_LOGGER_URL")

OWNER_ID : int = 812808602997620756
TEST_SERVER_ID = 915104477521014834

BOT_TOKEN = os.environ.get("TOKEN")