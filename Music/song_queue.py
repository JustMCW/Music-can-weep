import asyncio
import logging

from collections import deque

from typing import (
    Coroutine, 
    Callable, 
    Dict, 
    List, 
    Any, 
    Optional, 
    Union,
    TYPE_CHECKING
)
from typing_extensions import Self

import discord


from literals import ReplyEmbeds

from .song_track      import SongTrack,LiveStreamAudioSource,create_track_from_url
from .voice_utils     import clear_audio_message
from .voice_constants import *

import custom_errors

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if TYPE_CHECKING:
    from guildext import GuildExt

#TODO : guild.song_queue.audio_message != self.audio_message

hash_maps : Dict[int,Any] = {} #Multi-instances

class SongQueue(deque[SongTrack]):
    """
    A sub-class of `collections.deque`, for managing a list of `SongTracks`
    containing `SongTrack`s with different attributes and methods to work with.
    """
    def __init__(self, guild : 'GuildExt' ):
        self.guild = guild 
    
        self.volume  :float  = VOLUME_SCALE_FACTOR
        self.pitch   :float  = 1
        self.tempo   :float  = 1

        self.looping       :bool   = False
        self.queue_looping :bool   = False
        self.auto_play     :bool   = False

        self.audio_message :discord.Message = None

        self.history :list[SongTrack] = []

        self._event_loop = asyncio.get_running_loop()
        self._call_after :Callable = None

        super().__init__()

### Getting song track from the queue
    @classmethod
    def get_song_queue_for(cls, guild:discord.Guild) -> Self:
        search = hash_maps.get(guild.id)

        if search:
            return search

        #Create one if not found
        hash_maps[guild.id] = cls(guild)
        return hash_maps[guild.id]

    def get(self, __index: int) -> Optional[SongTrack]:
        """A method to get the track without having to worry about exception, 
        returns None if not found."""
        try: return self[__index]
        except IndexError: return None
    
    @property
    def current_track(self) -> SongTrack:
        return self.get(0)

### Properties of the queue

    @property
    def enabled(self) -> bool:
        return self.guild.database.get("queuing")

    @property
    def total_length(self) -> int:
        return sum( map( lambda t: t.duration, self ) ) 

    @property
    def time_position(self) -> int:
        """The time position, relative to the queue's tempo"""
        try:
            return self[0].time_position * self.tempo
        except (IndexError,AttributeError): 
            return 0
            
    @time_position.setter
    def time_position(self,new_tp):

        if new_tp > self.time_position:
            #Fast forwarding, loading unloaded audio
            wf = self[0].source.write_frame if self[0].seekable else self[0].source.original.read

            for _ in range(round((new_tp - self.time_position) / self.tempo * 50 )):
                try: 
                    wf()
                except AttributeError: 
                    break
        # We only want to disable rewinding
        elif not self[0].seekable:
            raise custom_errors.AudioNotSeekable("Audio is not seekable.")
        
        self[0].time_position = new_tp/self.tempo
        asyncio.get_running_loop().create_task(self.update_audio_message())

    @property
    def volume_percentage(self):
        return self.volume*100 / VOLUME_SCALE_FACTOR

    @volume_percentage.setter
    def volume_percentage(self, perc : Union[int,float]):
        self.volume = perc/100 * VOLUME_SCALE_FACTOR
        if self.guild.voice_client and self.guild.voice_client.source:
            self.guild.voice_client.source.volume = self.volume
            

### Modifying the queue

    def swap(self,pos1:int,pos2:int) -> None:
        
        if not self: 
            raise custom_errors.QueueEmpty("No tracks in the queue to be swapped")

        if pos1 == pos2:
            raise IndexError("Why try to swap the same item")

        if pos1 >= len(self) or pos1 == 0:
            raise IndexError(f"pos1 : {pos1} is invaild")
        
        if pos2 >= len(self) or pos2 == 0:
            raise IndexError(f"pos2 : {pos2} is invaild")

        self[pos1] , self[pos2] = self[pos2] , self[pos1]
    
    def shuffle(self) -> None:

        if not self: 
            raise custom_errors.QueueEmpty("No tracks in the queue to be shuffled")

        is_playing = self.guild.voice_client is not None and self.guild.voice_client.is_playing()
        
        #Exclude the first item ( currently playing )
        if is_playing:
            playing_track = self.popleft()
        
        from random import shuffle
        shuffle(self)
        
        #Add it back after shuffling
        if is_playing:
            self.appendleft(playing_track)

    def poplefttohistory(self) -> SongTrack:
        """Extension of popleft, the track popped is added to the history list, 
        also adds recommended track if no track is left fot some reason"""
        track = self.popleft()
        if len(self) == 0 and self.auto_play:
            self.append(
                create_track_from_url(track.recommend.url)
            )
        self.history.append(track)
        return track

    def shift_track(self, count=1):
        """Shifts track around, but does not remove any track.
        [1,2,3,4] => [2,3,4,1]
        
        Could also take negative input to shift in opposite direction"""
        def rotate_queue():
            self.rotate(count * -1)
            self.play_first()

        self._call_after = rotate_queue
        self.guild.voice_client.stop()

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
        self.guild.voice_client.stop()

    def skip_track(self, count=1):
        if self.queue_looping:
            return self.shift_track(count)

        def skip_after():
            for _ in range(count):
                try: 
                    self.poplefttohistory()
                except IndexError: 
                    break 
            
            if self.current_track:
                self.play_first()

        self._call_after = skip_after 
        self.guild.voice_client.stop()

    def replay_track(self):
        self._call_after = lambda: self.play_first()
        self.guild.voice_client.stop()

    async def cleanup(self) -> None:
        """Removes every track from the queue after some time, including the first one and disconnects from the voice."""
        guild = self.guild
        
        if self and self.guild.database.get("auto_clear_queue"):
            logger.info(f"Clearing queue after {CLEAR_QUEUE_AFTER}.")
            await asyncio.sleep(CLEAR_QUEUE_AFTER)
            
            self.clear()
        elif guild.voice_client:
            await guild.voice_client.disconnect()
### Playing tracks in the queue

    def play_first(self):
        """Plays the first track in the queue at the current voice channel, 
        or recommendation if it's enabled and no track is present
        
        while also appling the volume, pitch and tempo from the queue to the track, as well as the after function.
        """
        track = self.current_track
        track.play(
            self.guild.voice_client,
            after  = self.after_playing,

            volume = self.volume,
            pitch  = self.pitch ,
            tempo  = self.tempo ,
        )
        logger.info(f"Playing \"{track.title}\".")


    def after_playing(self,voice_error :str = None):
        """Handles everything that happenes after an audio track has ended"""

    ### Stuff that must be done after an audio ended : cleaning up the process and handling error(s)
        
        #AudioPlayer thread error, no trackback tho.
        if voice_error: 
            logger.exception("Voice error :",voice_error)

        finshed_track = self.current_track
        logger.info(f"Track finshed : {finshed_track.title}")

        #Moved cleanup here in order to access returncode of the ffmepg process.
        if not isinstance(finshed_track.source,LiveStreamAudioSource):
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
                await self.make_next_audio_message()

                if not self.current_track:
                    await self.guild.voice_client.disconnect()
                


            return self._event_loop.create_task(finish())

        #Wrapped here for coroutine functions to run.   
        #Didn't wrap the code above because create_task has a great delay but cleanup actions has to be done ASAP
        async def inner():
            logging.debug("Entered inner function.")
            finshed_track = self.current_track
            guild = self.guild
            voice_client : discord.VoiceClient = guild.voice_client
            
            #Not in voice channel
            if not voice_client or not voice_client.is_connected():
                await clear_audio_message(self)

                if not self.enabled:
                    self.poplefttohistory()

                await self.cleanup()
                return logger.info("Client is not in voice after playing.")
             

        ### Time to decide what the next track would be
            next_track : SongTrack = None

            #Single track looping is on
            if self.looping:
                next_track = finshed_track

            #Queuing disabled, don't even try to play anything.
            elif not self.enabled:
                self.poplefttohistory()
                await voice_client.disconnect()
                await clear_audio_message(self)
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
                    await clear_audio_message(self)
                    await voice_client.disconnect()

                    return logger.info("Queue is empty")

                #To prevent sending the same audio message again
                if next_track != finshed_track:
                    await self.make_next_audio_message()
                

        ### Finally, play the audio
            self.play_first()

        self._event_loop.create_task(inner())


### Audio messages

    async def make_next_audio_message(self):
        """Remove the current audio message and make a new one, can be editing or sending a new one."""

        next_track = self.current_track

        is_reply = self.audio_message.reference

        if next_track:

            if self.audio_message.embeds[0].url == next_track.webpage_url:
                return logger.debug("Track is the same, not updating")
            
            if (self.looping or self.queue_looping):

                if not is_reply:
                    if next_track.request_message:
                        await clear_audio_message(specific_message= next_track.request_message)
                        next_track.request_message = None
                    return await self.create_audio_message(self.audio_message)
            
        await clear_audio_message(self)
        
        if next_track:
            
            if next_track.request_message:
                await self.create_audio_message(next_track.request_message)   
                next_track.request_message = None
            elif is_reply:
                await self.create_audio_message(self.audio_message.channel)
            else:
                await self.create_audio_message(self.audio_message)

        else:
            self.audio_message = None

    async def update_audio_message(self):
        audio_msg = self.audio_message

        if not audio_msg: 
            return logger.warning("Audio message adsent when trying to update it.")

        from my_buttons import MusicButtons
        await audio_msg.edit(
            embed = ReplyEmbeds.audio_displayer(self),
            view = MusicButtons.AudioControllerButtons(self)
        )

    async def create_audio_message(self,target:Union[discord.TextChannel,discord.Message] = None):
        """
        Create the discord message for displaying audio playing, including buttons and embed
        accecpt a text channel or a message to be edited
        """
        if not self.current_track:
            return 
        
        from my_buttons import MusicButtons
        from literals   import ReplyEmbeds

        message_info = {
            "embed": ReplyEmbeds.audio_displayer(self),
            "view" : MusicButtons.AudioControllerButtons(self)
        }

        self.audio_view = message_info["view"]

        if isinstance(target,discord.Message):
            await target.edit(**message_info)
            self.audio_message = await target.channel.fetch_message(target.id)

        if isinstance(target,discord.TextChannel):
            self.current_track.request_message
            self.audio_message = await target.send(**message_info)

        #A thread that keeps updating the audio progress bar until the audio finishs
        t = self[0]

        if  not t.duration: 
            return 

        async def run():
            while self.get(0) == t: 

                if not self[0].source:
                    await asyncio.sleep(UPDATE_DELAY)
                    continue

                if not self.guild.voice_client:
                    break

                if not self.guild.voice_client.is_paused():
                    await self.update_audio_message()

                await asyncio.sleep(UPDATE_DELAY)

            logger.info("Exited update loop")

        self._event_loop.create_task(run())