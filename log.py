#Logs_channel_id
from datetime import datetime
import requests

from os import environ
running_locally = environ.get("TOKEN") is None

class Logging:
    @classmethod
    async def log(self,message:str):
        if not running_locally:
            requests.post("https://discord.com/api/webhooks/954928052767457350/BVexILQ8JmXeUKrR2WdWPkW6TSZVxTRsMYSqBsrbbkzdO6kc2uMnRB_UfpsH5rsMT0w-",
                          data = {
                            "content":f"`{datetime.now()}` - {message}"
                          })
        else:
            print(message)

    @classmethod
    async def error(self,error_message:str):
        print(error_message)
        requests.post("https://discord.com/api/webhooks/960588563026677840/5NVR3WZaFvbMaZTajbkIaxFrQcBjcFjArU7Zp3Ifd_vMolPlGbvphAelrHwajw07UuOg",
                      data = {
                        "content":f"`{datetime.now()}` - {error_message}"
                      })