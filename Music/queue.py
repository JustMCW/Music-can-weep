import discord,json

from Music.song_track import SongTrack
from errors import custom_errors
from main import BOT_INFO

from collections import deque

DiscordServerDatabase = "Database/DiscordServers.json"

class SongQueue(deque):
    def __init__(self,guild:discord.Guild=None):
        self.guild:discord.Guild = guild

        self.volume:float = BOT_INFO.InitialVolume
        self.audio_control_status:str = None

        self.looping:bool = BOT_INFO.InitialLooping
        self.queue_looping:bool = BOT_INFO.InitialQueueLooping

        self.audio_message:discord.Message = None

        self.player_loop_passed = []

        super().__init__()

    def get(self, __index: int) -> SongTrack:
        try:
            return self[__index]
        except IndexError:
            return None
    
    @property
    def enabled(self)->bool:
        with open(DiscordServerDatabase,"r") as SVDBjson_r:
            data = json.load(SVDBjson_r)[str(self.guild.id)]
        return data["queuing"]

    @property
    def total_length(self):
        total_len = 0
        
        for track in self:
            total_len += track.duration

        return total_len

    @property
    def time_position(self) -> int:
        if self.guild.voice_client.is_paused():
            extra = sum(self.player_loop_passed[:-1])
        else:
            extra = sum(self.player_loop_passed)
        return (self.guild.voice_client._player.loops + extra) // 50

    def swap(self,pos1:int,pos2:int):
        
        if len(self) ==0: 
            raise custom_errors.QueueEmpty

        #Swapping same item :/
        if pos1 == pos2:
            raise IndexError("Why try to swap the same item")

        if pos1 >= len(self) or pos1 == 0:
            raise IndexError(f"pos1 - {pos1} is invaild")
        
        if pos2 >= len(self) or pos2 == 0:
            raise IndexError(f"pos2 - {pos2} is invaild")

        self[pos1] , self[pos2] = self[pos2] , self[pos1]
    
    def shuffle(self):

        if len(self) ==0: 
            raise custom_errors.QueueEmpty

        #Exclude the first item ( currently playing )
        playing = self.popleft()
        
        from random import shuffle
        shuffle(self)
        
        #Add it back after shuffling
        self.appendleft(playing)

        