import discord
from discord.ext import commands
from collections import deque
from typing_extensions import Self

from main        import BOT_INFO

hash_maps = {}

class SongQueue(deque):
    def __init__(self,guild):
        self.guild                :discord.Guild   = guild 

        self.volume               :float           = BOT_INFO.InitialVolume
        self.audio_control_status :str             = None

        self.looping              :bool            = BOT_INFO.InitialLooping
        self.queue_looping        :bool            = BOT_INFO.InitialQueueLooping

        self.audio_message        :discord.Message = None

        self.player_loop_passed   :list            = []

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
    def sync_lyrics(self) -> bool:
        return self.guild.database.get("sync_lyrics")

    @property
    def total_length(self) -> int:
        return sum( map( lambda t: t.duration, self ) ) 

    @property
    def time_position(self) -> int:
        voicec    :discord.VoiceClient = self.guild.voice_client
        loop_pass :list                = self.player_loop_passed

        return (voicec._player.loops + sum(loop_pass[:-1] if voicec.is_paused() else loop_pass)) // 50

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

        