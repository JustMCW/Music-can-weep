import discord
import time
import asyncio
from discord.ext import commands
from collections.abc import Callable

from main import BOT_INFO
from Music.queue import Queue
from errors import custom_errors

#DECORATER
def playing_audio(vcfunc:Callable[[discord.Guild],None]):
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
    def is_playing(guild)-> bool:
        if not guild.voice_client: 
            return False
        return guild.voice_client.source is not None

    @classmethod
    def is_paused(self,guild)->bool:
        if not self.is_playing(guild):
            return True
        return guild.voice_client.is_paused()

    def get_now_playing(self,guild) -> dict:
        return self.now_playing.get(guild.id)

    def get_queue(self,guild) ->Queue:
        if self.queues.get(guild.id) is None:
            self.queues[guild.id] = Queue(guild)
        return self.queues.get(guild.id)

    def get_queue_loop(self,guild)->bool:
        return self.get_queue(guild).queue_looping

    def get_loop(self,guild)->bool:
        return self.get_queue(guild).looping
    
    @staticmethod
    def get_current_vc(guild)->discord.VoiceChannel:
        return guild.voice_client.channel
    
    def get_volume(self,guild)->float:
        return self.get_queue(guild).volume

    def get_volume_percentage(self,guild)->str:
        return f'{round(self.get_volume(guild) / BOT_INFO.InitialVolume * 100)}%'

    @staticmethod
    def get_non_bot_vc_members(guild)->list:
        if guild.voice_client:
            return [member for member in guild.voice_client.channel.members if not member.bot]
        return None
    
#

    @staticmethod
    async def join_voice_channel(guild:discord.Guild, vc):
        try:
            if guild.voice_client is None: 
                await vc.connect()
            else: 
                await guild.voice_client.move_to(vc)
        except: 
            raise commands.errors.BotMissingPermissions({"connect"})

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
                      after=lambda e: asyncio.run(self.after_playing(guild,new_start_time,e)) )