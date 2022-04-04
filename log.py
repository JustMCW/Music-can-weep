#Logs_channel_id
cmd_log_id = 923730161864704030
error_log_id = 923761805619232798
from datetime import datetime
import requests

class Logging:
  @classmethod
  async def log(self,message:str):
    
    requests.post(
      "https://discord.com/api/webhooks/954928052767457350/BVexILQ8JmXeUKrR2WdWPkW6TSZVxTRsMYSqBsrbbkzdO6kc2uMnRB_UfpsH5rsMT0w-",
      data = {
        "content":f"`{datetime.now()}` - {message}"
      })

  @classmethod
  async def error(self,error_message:str):
    print(error_message)
    requests.post(
      "https://discord.com/api/webhooks/960588563026677840/5NVR3WZaFvbMaZTajbkIaxFrQcBjcFjArU7Zp3Ifd_vMolPlGbvphAelrHwajw07UuOg",
      data = {
        "content":f"`{datetime.now()}` - {error_message}"
      })
    #f"```arm