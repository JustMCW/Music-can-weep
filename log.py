#Logs_channel_id
cmd_log_id = 923730161864704030
error_log_id = 923761805619232798

class Logging:
  @classmethod
  async def log(self,message:str):
    print(message)

  @classmethod
  async def error(self,error_message:str):
    print(error_message)
    #f"```arm