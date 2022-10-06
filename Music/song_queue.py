import discord
from discord.ext import commands
from collections import deque
from typing_extensions import Self
from typing import Deque, Dict, List,Any
from enum import Enum,auto
from youtube_utils import YoutubeVideo,get_recommendation

from main import BotInfo
from Music.song_track import SongTrack

hash_maps : Dict[int,Any] = {} #Multi-instances

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
        self.tempo                :float           = 1

        self.audio_control_status :AudioControlState = None

        self.looping              :bool            = BotInfo.InitialLooping
        self.queue_looping        :bool            = BotInfo.InitialQueueLooping
        self.auto_play            :bool            = True

        self.audio_message        :discord.Message = None

        self.history              :List[SongTrack] = []
        self._recommendations     :Deque[YoutubeVideo] = []

        super().__init__()

    @classmethod
    def get_song_queue_for(cls,guild:discord.Guild) -> Self:
        search = hash_maps.get(guild.id)

        if search is not None:
            return search
        #Create one if not found
        hash_maps[guild.id] = cls(guild)
        return hash_maps[guild.id]

    def get(self, __index: int):
        try: return self[__index]
        except IndexError: return None
    
    def append(self, track : SongTrack) -> None:
        super().append(track)
        if len(self) == 1 and self.auto_play:
            self.generate_rec()

    #Just typed it here
    def __getitem__(self, __index) -> SongTrack:
        return super().__getitem__(__index)

    def cleanup(self) -> None:
        if self.guild.voice_client: 
            self.audio_control_status = AudioControlState.CLEAR
            self.guild.voice_client.stop()

    @property
    def enabled(self) -> bool:
        return self.guild.database.get("queuing")

    @property
    def total_length(self) -> int:
        return sum( map( lambda t: t.duration, self ) ) 

    @property
    def time_position(self) -> int:
        """The time position, relative to it's tempo"""
        try:
            return self[0].time_position * self.tempo
        except IndexError:
            return None
            
    #[0].timeposition is frame count / 50, bascially real-time
    @time_position.setter
    def time_position(self,new_tp):

        if new_tp > self.time_position:
            #2 time speed, 1/2 duration
            loop = round((new_tp - self.time_position) / self.tempo * 50 )
            self._raw_fwd(loop)
        self[0].time_position = new_tp/self.tempo

    def generate_rec(self):
        rec = None
        while not rec:
            rec = get_recommendation(self[0].webpage_url)
        self._recommendations = deque(rec)

    @property
    def recommend(self) -> YoutubeVideo:
        if self.auto_play:
            return self._recommendations[0]
        raise AttributeError("Auto-play must be true in order to access recommendation")

    def _raw_fwd(self, counter : int):
        for _ in range(counter):
            try: 
                self[0].source.write_frame()
            except AttributeError: 
                return

    def play_first(self,voice_client:discord.VoiceClient):
        """
        Plays the first track in the queue, while also appling the volume, pitch and sound from the queue to the track
        """
        from Music.voice_state import after_playing
        import asyncio
        event_loop = asyncio.get_running_loop()

        event_loop.create_task(self[0].play(
            voice_client,
            after= lambda voice_error: after_playing(event_loop,voice_client.guild,voice_error),

            volume = self.volume,
            pitch  = self.pitch ,
            tempo  = self.tempo ,
        ))

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

