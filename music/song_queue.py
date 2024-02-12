import asyncio
import logging
import random

from collections import deque

from typing import (
    Callable, 
    Dict, 
    Optional, 
)

import discord

from .song_track import *

from .voice_utils import  playing_audio
from .audio_message import (
    update_audio_message,
    clear_audio_message_for_queue,
    clear_audio_message,
    make_next_audio_message
)
from .voice_constants import *

from typechecking import ensure_exist

from database.server import read_database_of
import custom_errors

logger = logging.getLogger(__name__)

#TODO : music.get_song_queue.audio_message != self.audio_message


class SongQueue(deque[SongTrack]):
    """
    A sub-class of `collections.deque`, for managing a list of `SongTracks`
    containing `SongTrack`s with different attributes and methods to work with.
    """
    def __init__(self, guild : discord.Guild ):
        self.guild = guild 
    
        self.volume  :float  = VOLUME_SCALE_FACTOR
        self.pitch   :float  = 1
        self.tempo   :float  = 1

        self.looping       :bool   = False
        self.queue_looping :bool   = False
        self.auto_play     :bool   = False

        self.audio_message :Optional[discord.Message] = None

        self.history :list[SongTrack] = []

        self._event_loop = asyncio.get_event_loop()
        self._call_after :Optional[Callable] = None
        self._after_flag :bool = False

        super().__init__()

    def get(self, __index: int) -> Optional[SongTrack]:
        """A method to get the track without having to worry about exception, 
        returns None if not found."""
        try: 
            return self[__index]
        except IndexError: 
            return None
    
    @property
    def voice_client(self) -> Optional[discord.VoiceClient]:
        if not isinstance(self.guild.voice_client, discord.VoiceClient) and self.guild.voice_client != None:
            raise RuntimeError("New voice protocol class is used.")
        return self.guild.voice_client

    @property
    def source(self) -> Optional['AudioSource']:
        if not self.voice_client:
            return None
        src = self.voice_client.source
        if isinstance(src, TimeFrameAudio):
            return src
        raise RuntimeError(f"Source is not a PCMVolumeTransformer : {src.__class__.__name__}")

    @property
    def current_track(self) -> Optional[SongTrack]:
        """returns the first track but doesn't trigger exception"""
        return self.get(0)

    @property
    def enabled(self) -> bool:
        return read_database_of(self.guild)["queuing"]

    @property
    def total_length(self) -> int:
        return sum( map( lambda t: t.duration, self ) ) 

    @property
    def time_position(self) -> float:
        """The time position, relative to the queue's tempo"""
        try:
            return self[0].time_position * self.tempo
        except (IndexError,AttributeError): 
            return 0
            
    @time_position.setter
    def time_position(self,new_tp):
        if not self.source:
            raise RuntimeWarning("Attempt to set time position without any tracks playing.")
        if isinstance(self.source, LiveStreamAudio):
            raise custom_errors.AudioNotSeekable("Audio is a live stream")
        if not isinstance(self.source, AudioSource):
            raise RuntimeError("Not time frame audio as source, don't call")

        if new_tp > self.time_position:
            #Fast forwarding, loading unloaded audio
            wf = self.source.write_frame 

            for _ in range(round((new_tp - self.time_position) / self.tempo * 50 )):
                try: 
                    wf()
                except AttributeError: 
                    break
        # We only want to disable rewinding
        elif not self.source.seekable:
            raise custom_errors.AudioNotSeekable("Audio is not seekable.")
        
        self[0].time_position = new_tp/self.tempo
        asyncio.get_running_loop().create_task(update_audio_message(self))

    @property
    def volume_percentage(self):
        return self.volume*100 / VOLUME_SCALE_FACTOR

    @volume_percentage.setter
    def volume_percentage(self, perc : int|float):
        self.volume = perc/100 * VOLUME_SCALE_FACTOR
        # Applying
        if self.source != None:
            self.source.volume = self.volume

    def set_flag(self) -> None:
        """Set a flag to let the after call acknowledge that the logic has been handled and it doesn't need to apply anymore"""
        self._after_flag = True

### Modifying the queue

    def swap(self, i: int, j: int) -> None:
        if not self: 
            raise custom_errors.QueueEmpty("No tracks in the queue to be swapped")

        self[i], self[j] = self[j], self[i]
    
    def shuffle(self) -> None:
        """this shuffle function is different in the sense that if the first track is playing, it does not change its position"""
        if not self: 
            raise custom_errors.QueueEmpty("No tracks in the queue to be shuffled")
        
        playing = self.source != None
        #Exclude the first item ( currently playing )
        if playing:
            playing_track = self.popleft()
        
        random.shuffle(self)
        
        #Add it back after shuffling
        if playing:
            self.appendleft(playing_track) 

    def poplefttohistory(self) -> SongTrack:
        """Extension of popleft, the track popped is added to the history list, 
        also adds recommended track if no track is left fot some reason"""
        track = self.popleft()

        # Adding auto play tracks
        if len(self) == 0 and self.auto_play:
            if isinstance(track,YoutubeTrack):
                self.append(create_track_from_url(track.recommend.url))
        self.history.append(track)
        return track

    
    def shift_track(self, count=1):
        """Shifts track around, but does not remove any track.
        [1,2,3,4] => [2,3,4,1]
        
        Could also take negative input to shift in opposite direction"""
        if not self.source:
            return self.rotate(count * -1)

        def rotate_queue():
            self.rotate(count * -1)
            self.play_first()

        self._call_after = rotate_queue
        self.guild.voice_client.stop() # type: ignore

    @playing_audio
    def rewind_track(self, count=1):
        """Add the latest history track to the front of the queue for an ammount, 
        does not raise any error when paramater `count` is greater than the length of the queue history"""

        if self.queue_looping and self[-1].source:
            return self.shift_track(count * -1)

        def rewind_after():
            for _ in range(count):
                try: self.appendleft(self.history.pop(-1))
                except IndexError: break
            self.play_first()

        self._call_after = rewind_after
        self.guild.voice_client.stop() #type: ignore

    @playing_audio
    def skip_track(self, count=1):
        if self.queue_looping:
            return self.shift_track(count)
        # if not self.guild.voice_client:
        #     raise custom_errors.NotInVoiceChannel
        
        def skip_after():
            for _ in range(count):
                try: 
                    self.poplefttohistory()
                except IndexError: 
                    break 
            
            if self.current_track:
                self.play_first()

        self._call_after = skip_after 
        self.guild.voice_client.stop() #type: ignore

    @playing_audio
    def replay_track(self):
        self._call_after = self.play_first
        self.guild.voice_client.stop() #type: ignore

    async def cleanup(self) -> None:
        """Removes every track from the queue after some time, including the first one and disconnects from the voice."""
        guild = self.guild

        
        if self and read_database_of(guild)["autoclearing"]:
            logger.info(f"Clearing queue after {CLEAR_QUEUE_AFTER}.")
            await asyncio.sleep(CLEAR_QUEUE_AFTER)
            
            self.clear()
        elif guild.voice_client:
            await guild.voice_client.disconnect() #type: ignore
### Playing tracks in the queue

    def play_first(self):
        """Plays the first track in the queue at the current voice channel, 
        or recommendation if it's enabled and no track is present
        
        while also appling the volume, pitch and tempo from the queue to the track, as well as the after function.
        """
        track = self.current_track

        if not track:
            return logger.error("No song track is in the queue")

        track.play(
            self.guild.voice_client, #type: ignore
            after  = self.after_playing,

            volume = self.volume,
            pitch  = self.pitch ,
            tempo  = self.tempo ,
        )
        logger.info(f"Playing \"{track.title}\".")

    async def after_playing_inner(self):
        """The logic when the rest of the condition is met (in vc, not return code 1)"""
        logging.debug("Entered inner function.")
        finshed_track = self.current_track
        guild = self.guild
        voice_client : discord.VoiceClient = guild.voice_client #type: ignore
        
        #Not in voice channel
        if not voice_client or not voice_client.is_connected():
            await clear_audio_message_for_queue(self)

            if not self.enabled:
                self.poplefttohistory()

            await self.cleanup()
            return logger.info("Client is not in voice after playing.")
            

    ### Time to decide what the next track would be
        next_track = finshed_track

        #Single track looping is on
        if self.looping:
            pass

        #Queuing disabled, don't even try to play anything.
        elif not self.enabled:
            self.poplefttohistory()
            await voice_client.disconnect()
            await clear_audio_message_for_queue(self)
            return logger.info("Queue disabled")

        #The rest of the situation, lol.
        else:
            self[0].request_message = None
            
            #Shifting the tracks, or popping
            if self.queue_looping: 
                self.rotate(-1)    
            else: 
                self.poplefttohistory()
        
            #Get the next track ( first track in the queue )
            next_track = self.current_track

            #No track left in the queue
            if next_track is None:
                # await text_channel.send("\\☑️ All tracks in the queue has been played (if you want to repeat the queue, run \" >>queue repeat on \")",delete_after=30)
                await clear_audio_message_for_queue(self)
                await voice_client.disconnect()

                return logger.info("Queue is empty")

            #To prevent sending the same audio message again
            if next_track != finshed_track:
                await make_next_audio_message(self)
            
            
    ### Finally, play the audio
        self.play_first()

    def after_playing(self, voice_error :Optional[str] = None):
        """Handles everything that happenes after an audio track has ended"""

    ### Stuff that must be done after an audio ended : cleaning up the process and handling error(s)
        
        #AudioPlayer thread error, no trackback tho.
        if voice_error: 
            logger.exception("Voice error :",voice_error)

        finshed_track = self.current_track

        if finshed_track is None:
            return logger.warning("Track finished not found")

        logger.info(f"Track finshed : {finshed_track.title}")

        #Moved cleanup here in order to access returncode of the ffmepg process.
        if not isinstance(finshed_track.source,LiveStreamAudio):
            finshed_track.source.original.cleanup()
            returncode = finshed_track.source.original.returncode

            # Recreate the source and process if ffmpeg returned 1
            if returncode == 1:
                logger.warning("FFmpeg process returned 1, retrying...") 
                self[0] = create_track_from_url(
                    finshed_track.webpage_url, 
                    finshed_track.requester, 
                    finshed_track.request_message
                )
                return self.play_first()

        #Calling the after function
        if self._call_after: 

            logger.info(f"Calling after function : \"{self._call_after.__name__}\".")
            self._call_after()
            self._call_after = None

            async def finish():
                await make_next_audio_message(self)

                if not self:
                    await self.guild.voice_client.disconnect() #type: ignore

            return self._event_loop.create_task(finish())

        #Wrapped here for coroutine functions to run.   
        #Didn't wrap the code above because create_task has a great delay but cleanup actions has to be done ASAP
        self._event_loop.create_task(self.after_playing_inner())



#Multi-instances
queue_hash : Dict[int, SongQueue] = {} 

def get_song_queue(guild: Optional[discord.Guild]) -> SongQueue:
    guild = ensure_exist(guild)
    search = queue_hash.get(guild.id)
    
    if search is not None:
        return search

    #Create one if not found
    logger.info(f"Creating a new queue object for guild {guild.id}")
    instance = SongQueue(guild) #type: ignore
    queue_hash[guild.id] = instance
    return instance
