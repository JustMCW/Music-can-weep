import asyncio
import logging

from math import floor
from collections import deque
from typing_extensions import Self
from typing            import Coroutine, Callable, Dict, List, Any, Optional, Union

import discord
from discord.ext import commands

from .song_track  import SongTrack,AutoPlayUser
import Convert
from string_literals import MyEmojis

VOLUME_WHEN_HUNDRED = 0.5
VOLUME_PERCENTAGE_LIMIT = 400
CLEAR_AFTER = 600
UPDATE_FREQUENCY = 25
UPDATE_DELAY = 3

hash_maps : Dict[int,Any] = {} #Multi-instances

class SongQueue(deque):
    """A sub-class of `collections.deque`, containing `SongTrack`s with different attributes and methods to work with."""
    def __init__(self,guild :discord.Guild ):
        self.guild       = guild 
        self._event_loop = asyncio.get_running_loop()
    
        self.volume               :float  = VOLUME_WHEN_HUNDRED
        self.pitch                :float  = 1
        self.tempo                :float  = 1

        self.looping              :bool   = False
        self.queue_looping        :bool   = False
        self.auto_play            :bool   = False

        self.audio_message        :discord.Message = None
        self.history              :List[SongTrack] = []
        self.call_after           :Callable        = None

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

    #Typing for items
    def __getitem__(self, __index) -> SongTrack:
        return super().__getitem__(__index)

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
            raise commands.errors.AudioNotSeekable("Audio is not seekable.")
        
        self[0].time_position = new_tp/self.tempo
        asyncio.get_running_loop().create_task(self.update_audio_message())


    @property
    def volume_percentage(self):
        return self.volume*100 / VOLUME_WHEN_HUNDRED

    @volume_percentage.setter
    def volume_percentage(self, perc : Union[int,float]):
        self.volume = perc/100 * VOLUME_WHEN_HUNDRED
        if self.guild.voice_client and self.guild.voice_client.source:
            self.guild.voice_client.source.volume = self.volume
            

### Modifying the queue

    def swap(self,pos1:int,pos2:int) -> None:
        
        if not self: 
            raise commands.errors.QueueEmpty("No tracks in the queue to be swapped")

        if pos1 == pos2:
            raise IndexError("Why try to swap the same item")

        if pos1 >= len(self) or pos1 == 0:
            raise IndexError(f"pos1 : {pos1} is invaild")
        
        if pos2 >= len(self) or pos2 == 0:
            raise IndexError(f"pos2 : {pos2} is invaild")

        self[pos1] , self[pos2] = self[pos2] , self[pos1]
    
    def shuffle(self) -> None:

        if not self: 
            raise commands.errors.QueueEmpty("No tracks in the queue to be shuffled")

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
            self.append(SongTrack.create_track(track.recommend.url,requester=AutoPlayUser))
        self.history.append(track)
        return track

    async def cleanup(self) -> None:
        """Removes every track from the queue after some time, including the first one and disconnects from the voice."""
        guild = self.guild
        
        if self and self.guild.database.get("auto_clear_queue"):
            logging.info(f"Wait for {CLEAR_AFTER} sec then clear queue")
            await asyncio.sleep(CLEAR_AFTER)
            
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
        logging.info(f"Play first track : {track.title}")
        track.play(
            self.guild.voice_client,
            after  = self.after_playing,

            volume = self.volume,
            pitch  = self.pitch ,
            tempo  = self.tempo ,
        )

    #Warning : You are about to enter the most chaotic code in my project, but also one of the most important bit.
    def after_playing(self,voice_error :str = None):
        """Handles everything that happenes after an audio track has ended"""

        from .voice_state import clear_audio_message
    ### Stuff that must be done after an audio ended : cleaning up the process and handling error(s)
        
        #AudioPlayer thread error, no trackback tho.
        if voice_error: 
            logging.exception("Voice error :",voice_error)

        FinshedTrack = self.get(0)
        logging.info(f"Track finshed : {FinshedTrack.title}")

        #Moved here in order to access returncode of the ffmepg process.
        FinshedTrack.source.original.cleanup()
        returncode = FinshedTrack.source.original.returncode

        # Recreate the source and process if ffmpeg returned 1
        if returncode == 1:
            logging.warning("FFmpeg process returned 1, recreating song_track.") 
            FinshedTrack.recreate_source_url()
            return self.play_first()

        #Calling the after function
        afterfunc = self.call_after
        if afterfunc: 

            afterfunc = afterfunc()
            self.call_after = None
            if isinstance(afterfunc,Coroutine):
                self._event_loop.create_task(afterfunc)
            return logging.info("Called after function.")

        #Wrapped here for coroutine functions to run.   
        #Didn't wrap the code above because create_task has a great delay but cleanup actions has to be done ASAP
        async def inner():
            guild = self.guild
            voice_client : discord.VoiceClient = guild.voice_client
            
            #Not in voice channel
            if not voice_client or not voice_client.is_connected():
                await clear_audio_message(guild)

                if not self.enabled:
                    self.poplefttohistory()

                await self.cleanup()
                return logging.info("Client is not in voice after playing.")
             

        ### Time to decide what the next track would be
            NextTrack : SongTrack = None

            #Single track looping is on
            if self.looping:
                NextTrack = FinshedTrack

            #Queuing disabled, don't even try to play anything.
            elif not self.enabled:
                self.poplefttohistory()
                await clear_audio_message(guild)
                return logging.info("Queue disabled")

            #The rest of the situation, lol.
            else:
                self[0].request_message = None
                
                #Shifting the tracks, or popping
                if self.queue_looping: 
                    self.rotate(-1)    
                else: 
                    self.poplefttohistory()
            
                #Get the next track ( first track in the queue )
                NextTrack = self.current_track

                #No track left in the queue
                if NextTrack is None:
                    # await text_channel.send("\\☑️ All tracks in the queue has been played (if you want to repeat the queue, run \" >>queue repeat on \")",delete_after=30)
                    await clear_audio_message(guild)
                    return logging.info("Queue is empty")

                #To prevent sending the same audio message again
                if NextTrack != FinshedTrack:
                    await self.make_next_audio_message()
                

        ### Finally, play the audio
            self.play_first()

        self._event_loop.create_task(inner())


### Audio messages
    @property
    def audio_message_embed(self) -> discord.Embed:
        """the discord embed for displaying the audio that is playing"""
        current_track = self.current_track

        if not current_track:
            return logging.warning("No track is in the queue, thus unable to create an embed for it.")

        #Init embed + requester header + thumbnail
        rembed = discord.Embed( title= current_track.title,
                                url= current_track.webpage_url,
                                color=discord.Color.from_rgb(255, 255, 255) ) \
                .set_author(name=f"Requested by {current_track.requester.display_name}" ,
                            icon_url=current_track.requester.display_avatar ) \
                .set_image( url=current_track.thumbnail )

        #Author field
        YT_creator = getattr(current_track,"channel",None)
        Creator = YT_creator or getattr(current_track,"uploader",None)
        if YT_creator or Creator:
            Creator_url = getattr(current_track,"channel_url",getattr(current_track,"uploader_url",None))
            Creator = "[{}]({})".format(Creator,Creator_url) if Creator_url else Creator

            rembed.add_field(name=f"{MyEmojis.YOUTUBE_ICON} YT channel" if YT_creator else "💡 Creator",
                             value=Creator)
        
        emoji_before = "━" or '🟥' 
        emoji_mid = "●"
        emoji_after = "━" or '⬜️'
        #Durartion field + Progress bar
        if current_track.duration:
            try:
                progress = max(floor((self.time_position / current_track.duration) * UPDATE_FREQUENCY),1)
            except AttributeError:
                progress = 1
            progress_bar = (emoji_before * (progress-1)) + emoji_mid + emoji_after * (UPDATE_FREQUENCY-progress)
            duration_formmated = Convert.length_format(current_track.duration)
            rembed.add_field(name="↔️ Length",
                             value=f'`{duration_formmated}`')
            rembed.set_footer(text=f"{Convert.length_format(self.time_position)} [ {progress_bar} ] {duration_formmated}")

            rembed.add_field(name="📝 Lyrics",
                             value=f"*Available in {len(current_track.subtitles)} languages*" if getattr(current_track,"subtitles",None) else "*Unavailable*")
        elif current_track.is_livestream:
            rembed.add_field(name="↔️ Time-lapse",
                             value=f'`{current_track.time_lapse_frame // 50}`')

        # these are always added
        rembed.add_field(name="📶 Volume ",
                            value=f"`{self.volume_percentage}%`")\
                .add_field(name="⏩ Tempo",
                            value=f"`{self.tempo:.2f}`")\
                .add_field(name="ℹ️ Pitch",
                            value=f'`{self.pitch:.2f}`')\
                \
                .add_field(name="🔊 Voice Channel",
                            value=f"{self.guild.voice_client.channel.mention}")\
                .add_field(name="🔂 Looping",
                            value=f'**{Convert.bool_to_str(self.looping)}**' if not current_track.is_livestream else "Livestream" ) \
                .add_field(name="🔁 Queue looping",
                            value=f'**{Convert.bool_to_str(self.queue_looping)}**')\
                
        if self.get(1):
            rembed.add_field(name="🎶 Upcoming track",value=self[1].title)
        elif self.auto_play and not self.queue_looping:
            rembed.add_field(name="🎶 Upcoming track (Auto play)",value= current_track.recommend.title)

        return rembed

    async def make_next_audio_message(self):
        """Remove the current audio message and make a new one, can be editing or sending a new one."""
        from .voice_state import clear_audio_message

        target : Union[discord.Message,discord.TextChannel] = self.audio_message.channel
        next_track = self[0]
        async for msg in target.history(limit = 3):

            if msg.id == self.audio_message.id:
                
                #if within 3 message, found the now playing message then use that as the target for editing
                if self.audio_message.reference is None:
                    target = await target.fetch_message(msg.id)

        if next_track.request_message:
            await next_track.request_message.delete()
            next_track.request_message = None

        if isinstance(target,discord.TextChannel): #
            await clear_audio_message(self.guild)
                
        await self.create_audio_message(target)

    async def update_audio_message(self):
        audio_msg = self.audio_message

        if not audio_msg: 
            return logging.warning("Audio message adsent when trying to update it.")

        from my_buttons import MusicButtons
        await audio_msg.edit(
            embed = self.audio_message_embed,
            view = MusicButtons.AudioControllerButtons(self)
        )


    async def create_audio_message(self,target:Union[discord.TextChannel,discord.Message] = None):
        """
        Create the discord message for displaying audio playing, including buttons and embed
        accecpt a text channel or a message to be edited
        """
        from my_buttons import MusicButtons

        message_info = {
            "embed": self.audio_message_embed,
            "view": MusicButtons.AudioControllerButtons(self)
        }

        if isinstance(target,discord.Message):
            await target.edit(**message_info)
            self.audio_message = await target.channel.fetch_message(target.id)

        if isinstance(target,discord.TextChannel):
            self.audio_message = await target.send(**message_info)

        #A thread that keeps updating the audio progress bar until the audio finishs
        t = self[0]

        if t.is_livestream or not t.duration: 
            return 

        async def run():
            last_tp = 1
            while self.get(0) == t: 
                if not self[0].source:
                    # time.sleep(UPDATE_DELAY)
                    await asyncio.sleep(UPDATE_DELAY)
                    continue
                

                if not self.guild.voice_client.is_paused():
                    await self.update_audio_message()
                await asyncio.sleep(UPDATE_DELAY)
                # time.sleep(max(self[0].duration/UPDATE_FREQUENCY,2))


        self._event_loop.create_task(run())