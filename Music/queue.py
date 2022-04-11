import discord,json

from Music.song_track import SongTrack
from errors import custom_errors
from main import BOT_INFO

from collections import deque

DiscordServerDatabase = "Database/DiscordServers.json"

def require_queue_enabled(func):
    def wrapper(self,*args,**kwargs):
        if not self.enabled:
            raise custom_errors.QueueDisabled
        func(self,*args,**kwargs)
    return wrapper

class SongQueue:
    def __init__(self,guild:discord.Guild=None):
        self.guild = guild

        self.volume:float = BOT_INFO.InitialVolume
        self.audio_control_status:str = None

        self.looping:bool = BOT_INFO.InitialLooping
        self.queue_looping:bool = BOT_INFO.InitialQueueLooping

        self.audio_message:discord.Message = None
        self._queue:list = []

    def __str__(self) -> str:
        return str(self._queue)
    
    def __getitem__(self,index:int) -> SongTrack:
        try:
            return self._queue[index]
        except IndexError:
            return None

    def __len__(self) -> int:
        return len(self._queue)
    
    def __iter__(self) -> iter:
        return iter(self._queue)

    def __iadd__(self,newTrack:SongTrack):
        self._queue.append(newTrack)
        return self

    def __isub__(self,pos:int):
        self._queue.pop(pos)
        return self
    
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

    @require_queue_enabled
    def move_first_to_last(self):
        self += self._queue.pop(0)
    
    @require_queue_enabled
    def move_last_to_first(self):
        self._queue.insert(0,self._queue.pop(-1))

    @require_queue_enabled
    def insert(self,track:SongTrack,pos:int):
        self._queue.insert(pos,SongTrack)

    @require_queue_enabled
    def swap(self,pos1:int,pos2:int):
        
        if len(self._queue) ==0: 
            raise custom_errors.QueueEmpty

        #Swapping same item :/
        if pos1 == pos2:
            raise IndexError("Why try to swap the same item")

        if pos1 >= len(self) or pos1 == 0:
            raise IndexError(f"pos1 - {pos1} is invaild")
        
        if pos2 >= len(self) or pos2 == 0:
            raise IndexError(f"pos2 - {pos2} is invaild")

        self._queue[pos1] , self._queue[pos2] = self._queue[pos2] , self._queue[pos1]
    
    @require_queue_enabled
    def shuffle(self):

        if len(self._queue) ==0: 
            raise custom_errors.QueueEmpty

        #Exclude the first item ( playing )
        queue_copy = self._queue[1:]
        
        from random import shuffle
        shuffle(queue_copy)
        
        #Add it back after shuffling
        queue_copy.insert(0,self._queue[0])

        self._queue = queue_copy
        
    def clear(self):
        self._queue.clear()