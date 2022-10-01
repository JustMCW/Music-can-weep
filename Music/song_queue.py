import discord
from discord.ext import commands
from collections import deque
from typing_extensions import Self
from typing import List
from enum import Enum,auto

from main import BotInfo
from Music.song_track import SongTrack
hash_maps = {}

class AudioControlState(Enum):
    REWIND = auto()
    SKIP = auto()
    RESTART = auto()
    CLEAR = auto()

class SongQueue(deque):
    def __init__(self,guild):
        self.guild                :discord.Guild   = guild 

        self.volume               :float           = BotInfo.InitialVolume

        self.pitch                :float           = 1
        self.speed                :float           = 1

        self.audio_control_status :AudioControlState = None

        self.looping              :bool            = BotInfo.InitialLooping
        self.queue_looping        :bool            = BotInfo.InitialQueueLooping

        self.audio_message        :discord.Message = None

        self.history              :List[SongTrack] = []

        super().__init__()

    @classmethod
    def get_song_queue_for(cls,guild:discord.Guild) -> Self:
        search = hash_maps.get(guild.id)

        if search is not None:
            return search
        
        hash_maps[guild.id] = cls(guild)
        return hash_maps[guild.id]

    def get(self, __index: int):
        try: return self[__index]
        except IndexError: return None
    
    @property
    def enabled(self) -> bool:
        return self.guild.database.get("queuing")

    @property
    def total_length(self) -> int:
        return sum( map( lambda t: t.duration, self ) ) 

    @property
    def time_position(self) -> int:
        try:
            return self[0].time_position * self.speed
        except IndexError:
            return None

    def _raw_fwd(self,loop_count : int):

        voicec = self.guild.voice_client
        for _ in range(loop_count):
            try: voicec.source.read()
            except AttributeError: break

    def play_first(self,voice_client:discord.VoiceClient,**kwargs):
        """
        Plays the first track in the queue, while also appling the volume, pitch and sound from the queue to the track
        """
        from Music.voice_state import after_playing
        import time
        import asyncio

        start_time = float(time.perf_counter())
        event_loop = asyncio.get_running_loop()


        self[0].play(
            voice_client,
            after= lambda voice_error: after_playing(event_loop,
                                                    voice_client.guild,
                                                    start_time,
                                                    voice_error),

            volume = self.volume,
            pitch  = self.pitch ,
            speed  = self.speed ,

            **kwargs
        )

    def swap(self,pos1:int,pos2:int) -> None:
        
        if not self: 
            raise commands.errors.QueueEmpty("No tracks in the queue to be swapped")

        #Swapping same item :/
        if pos1 == pos2:
            raise IndexError("Why try to swap the same item")

        if pos1 >= len(self) or pos1 == 0:
            raise IndexError(f"pos1 - {pos1} is invaild")
        
        if pos2 >= len(self) or pos2 == 0:
            raise IndexError(f"pos2 - {pos2} is invaild")

        self[pos1] , self[pos2] = self[pos2] , self[pos1]
    
    def shuffle(self) -> None:

        if not self: 
            raise commands.errors.QueueEmpty("No tracks in the queue to be shuffled")

        is_playing = self.guild.voice_client is not None and self.guild.voice_client.is_playing()
        
        if is_playing:
             #Exclude the first item ( currently playing )
            playing = self.popleft()
        
        from random import shuffle
        shuffle(self)
        
        if is_playing:
            #Add it back after shuffling
            self.appendleft(playing)

        