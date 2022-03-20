from convert import Convert
from main import BOT_INFO

from Music.queue import Queue

class VoiceState:

  @staticmethod
  def is_playing(guild)-> bool:
    if not guild.voice_client: return False
    return guild.voice_client.source is not None

  @classmethod
  def is_paused(self,guild)->bool:
    if not self.is_playing(guild):return False
    return guild.voice_client.is_paused()

  @staticmethod
  def get_non_bot_vc_members(guild):
    if guild.voice_client:
      return [member for member in guild.voice_client.channel.members if not member.bot]
    return None

  def get_now_playing(self,guild) -> dict:
    return self.now_playing.get(guild.id)

  def get_queue(self,guild):
    if self.queues.get(guild.id) is None:
      self.queues[guild.id] = Queue()
    return self.queues.get(guild.id)

  def get_loop(self,guild)->bool:
    return self.get_queue(guild).looping

  def get_deco_loop(self,guild)->str:
    return Convert.bool_to_str(self.get_loop(guild))
  
  @staticmethod
  def get_current_vc(guild):
    return guild.voice_client.channel

  
  def get_volume(self,guild)->float:
    return self.get_queue(guild).volume

  
  def get_volume_percentage(self,guild)->str:
    return f'{round(self.get_volume(guild) / BOT_INFO.InitialVolume * 100)}%'