from xml.dom.minidom import Attr
import discord
import time
import asyncio
from discord.ext import commands

from main import BOT_INFO
from Music.queue import SongQueue
from errors import custom_errors

#DECORATER
def playing_audio(vcfunc):
  async def wrapper(*args,**kwargs):
      guild = args[-1] if isinstance(args[-1],discord.Guild) else kwargs.get("guild")
      try:
          if guild.voice_client.source: 
              return await vcfunc(*args,**kwargs)
          else: 
              raise custom_errors.NoAudioPlaying
      except AttributeError: 
          raise custom_errors.NotInVoiceChannel
      
  return wrapper

class VoiceState:

    @staticmethod
    def is_playing(guild:discord.Guild)-> bool:
        if not guild.voice_client: 
            return False
        return guild.voice_client.source is not None

    @classmethod
    def is_paused(self,guild:discord.Guild)->bool:
        if not self.is_playing(guild):
            return True
        return guild.voice_client.is_paused()

    def get_now_playing(self,guild:discord.Guild) -> dict:
        return self.now_playing.get(guild.id)

    def get_queue(self,guild:discord.Guild) ->SongQueue:
        if self.queues.get(guild.id) is None:
            self.queues[guild.id] = SongQueue(guild)
        return self.queues.get(guild.id)

    def get_queue_loop(self,guild:discord.Guild)->bool:
        return self.get_queue(guild).queue_looping

    def get_loop(self,guild:discord.Guild)->bool:
        return self.get_queue(guild).looping
    
    @staticmethod
    def get_current_vc(guild:discord.Guild)->discord.VoiceChannel:
        try:
            return guild.voice_client.channel
        except AttributeError:
            return None
    
    def get_volume(self,guild:discord.Guild)->float:
        return self.get_queue(guild).volume

    def get_volume_percentage(self,guild:discord.Guild)->str:
        return f'{round(self.get_volume(guild) / BOT_INFO.InitialVolume * 100)}%'

    @staticmethod
    def get_non_bot_vc_members(guild:discord.Guild)->list:
        try:
            return [member for member in guild.voice_client.channel.members if not member.bot]
        except AttributeError:
            raise custom_errors.NotInVoiceChannel
    
#

    @staticmethod
    async def join_voice_channel(guild:discord.Guild, vc):
        if guild.voice_client is None: 
            await vc.connect()
        else: 
            await guild.voice_client.move_to(vc)

    @staticmethod
    @playing_audio
    async def pause_audio(guild:discord.Guild):
        guild.voice_client.pause()

    @staticmethod
    @playing_audio
    async def resume_audio(guild:discord.Guild):
        guild.voice_client.resume()
    
    @playing_audio
    async def rewind_audio(self,guild:discord.Guild):
        queue = self.get_queue(guild)
         
        queue.audio_control_status = "REWIND"

        guild.voice_client.stop()

    @playing_audio
    async def skip_audio(self,guild:discord.Guild):

        queue = self.get_queue(guild)

        queue.audio_control_status = "SKIP"
        guild.voice_client.stop()

    @playing_audio
    async def restart_audio(self,guild:discord.Guild):

        voice_client = guild.voice_client

        queue = self.get_queue(guild)

        queue.audio_control_status = "RESTART"

        voice_client.stop()
        
        new_start_time =float(time.perf_counter())
        queue[0].play(voice_client,
                      volume=queue.volume,
                      after= lambda voice_error: asyncio.run(self.after_playing(guild,new_start_time,voice_error)) )