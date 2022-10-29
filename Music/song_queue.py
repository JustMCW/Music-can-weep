import asyncio
import logging

import discord
from discord.ext import commands

from collections import deque
from typing_extensions import Self
from typing            import Coroutine, Callable, Deque, Dict, List, Any, Optional, Union

from youtube_utils    import YoutubeVideo,get_recommendation
from .song_track  import SongTrack,AutoPlayUser
import convert
from string_literals import MyEmojis

VOLUME_WHEN_HUNDRED = 0.5
VOLUME_PERCENTAGE_LIMIT = 400

hash_maps : Dict[int,Any] = {} #Multi-instances

class SongQueue(deque):
    """A sub-class of `collections.deque`, containing `SongTrack`s and different attributes to work with."""
    def __init__(self,guild):
        self.guild                :discord.Guild   = guild 
        self._event_loop          :asyncio.AbstractEventLoop = asyncio.get_running_loop()
    
        self.volume               :float           = VOLUME_WHEN_HUNDRED
        self.pitch                :float           = 1
        self.tempo                :float           = 1

        self.looping              :bool            = False
        self.queue_looping        :bool            = False
        self.auto_play            :bool            = False

        self.audio_message        :discord.Message = None

        self.history              :List[SongTrack] = []
        self._recommendations     :Deque[YoutubeVideo] = deque()
        self.call_after           : Callable[[],Union[None,Coroutine]] = None

        super().__init__()

### Getting stuff
    @classmethod
    def get_song_queue_for(cls,guild:discord.Guild) -> Self:
        search = hash_maps.get(guild.id)

        if search is not None:
            return search
        #Create one if not found
        hash_maps[guild.id] = cls(guild)
        return hash_maps[guild.id]

    def get(self, __index: int) -> Optional[SongTrack]:
        try: return self[__index]
        except IndexError: return None
    
    @property
    def current_track(self):
        try:
            return self[0]
        except IndexError:
            if self.auto_play:
                rec_track = SongTrack.create_track(query=self.recommend.url,requester=AutoPlayUser)
                self.append(rec_track)
                self._recommendations.clear()
                return rec_track
            else:
                return None

    #Just typed it here
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
        """The time position, relative to it's tempo"""
        try:
            return self[0].time_position * self.tempo
        except IndexError:
            return None
            
    #[0].timeposition is frame count / 50, bascially real-time
    @time_position.setter
    def time_position(self,new_tp):

        if new_tp > self.time_position:
            #Fast forwarding, loading unloaded aufdio
            wf = self[0].source.write_frame if self[0].seekable else self[0].source.original.read
            #2 time speed, 1/2 duration
            for _ in range(round((new_tp - self.time_position) / self.tempo * 50 )):
                try: 
                    wf()
                except AttributeError: 
                    break
        elif not self[0].seekable:
            raise commands.errors.AudioNotSeekable("Audio is not seekable.")
        self[0].time_position = new_tp/self.tempo

    @property
    def volume_percentage(self):
        return self.volume*100 / VOLUME_WHEN_HUNDRED

    @volume_percentage.setter
    def volume_percentage(self, perc : Union[int,float]):
        self.volume = perc/100 * VOLUME_WHEN_HUNDRED
        if self.guild.voice_client.source:
            self.guild.voice_client.source.volume = self.volume
            

    def _generate_rec(self):
        rec = None
        while not rec:
            rec = get_recommendation(self[0].webpage_url)
        self._recommendations = deque(rec)

    @property
    def recommend(self) -> YoutubeVideo:
        if self.auto_play:
            try:
                return self._recommendations[0]
            except IndexError:
                self._generate_rec()
                return self._recommendations[0]
        raise AttributeError("Auto-play must be true in order to access recommendation")

### Modifying the queue itself

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

    def poplefttohistory(self) -> SongTrack:
        """Extension of popleft, the track popped is added to the history list."""
        track = self.popleft()
        self.history.append(track)
        return track

    async def cleanup(self) -> None:
        """Removes every track from the queue, including the first one and disconnect from the voice."""
        guild = self.guild
        clear_after = 600
        
        if self and self.guild.database.get("auto_clear_queue"):
            logging.info(f"Wait for {clear_after} sec then clear queue")
            await asyncio.sleep(clear_after)
            
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

    def after_playing(self,voice_error :str = None):
        """Handles most thing that happenes after an audio track has ended"""
        #Warning : You are about to enter the most chaotic code in my whole project, but also one of the most important bit.
        from .voice_state import clear_audio_message
    ### Stuff that must be done after an audio ended no matter what : cleaning up the process and handling error(s)
        
        #AudioPlayer thread error, no trackback tho.
        if voice_error: 
            logging.exception("Voice error :",voice_error)

        FinshedTrack = self.get(0)
        logging.info(f"Track finshed : {FinshedTrack.title}")

        FinshedTrack.source.original.cleanup() #Moved here to access returncode
        returncode = FinshedTrack.source.original.returncode

        #403 forbidden error (most likely to be it when 1 is returned), get a new piece of info and replay it.
        if returncode == 1:
            logging.warning("FFmpeg process returned 1, regenerating song track format.") 
            #Get a new piece of info
            NextTrack = SongTrack.create_track(query = FinshedTrack.webpage_url,
                                                requester=FinshedTrack.requester,
                                                request_message=FinshedTrack.request_message)
            #Replace the old info
            self[0].formats = NextTrack.formats
            return self.play_first()
        elif FinshedTrack is None:
            return logging.warning("Queue is already empty before after is run.")

        #Call after function
        afterfunc = self.call_after
        if afterfunc: 
            afterfunc = afterfunc()
            self.call_after = None # Remove it
            if isinstance(afterfunc,Coroutine):
                self._event_loop.create_task(afterfunc)
            return logging.info("After function called and returning")

        async def inner(): #I must wrap this here because create_task has huge delay and the code above needs to run ASAP after 
            guild = self.guild
            voice_client : discord.VoiceClient = guild.voice_client
            #Not in voice channel
            if not voice_client or not voice_client.is_connected():
                await clear_audio_message(guild)

                if not self.enabled:
                    self.poplefttohistory()

                await self.cleanup()
                return logging.info("Client is not in voice after playing.")
             

        ### Time to decide what the next track would be played
            NextTrack     : SongTrack           = None
            #Single song looping is on
            if self.looping:
                NextTrack = FinshedTrack
            #Queuing disabled, don't even try to play.
            elif not self.enabled:
                self.poplefttohistory()
                await clear_audio_message(guild)
                return logging.info("Queue disabled")
            #The rest of the situation, lol.
            else:

                self[0].request_message = None
                
                #Shifting the tracks
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

                #To prevent sending the same audio message again, it can be very anoyying to get spammed.
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
            return print("No track is in the queue, thus unable to create an embed for it.")

        YT_creator = getattr(current_track,"channel",None) 
        Creator = YT_creator or getattr(current_track,"uploader")
        Creator_url = getattr(current_track,"channel_url",getattr(current_track,"uploader_url",None))
        Creator = "[{}]({})".format(Creator,Creator_url) if Creator_url else Creator

        rembed = discord.Embed(title= current_track.title,
                            url= current_track.webpage_url,
                            color=discord.Color.from_rgb(255, 255, 255))\
                \
                .set_author(name=f"Requested by {current_track.requester.display_name}",
                            icon_url=current_track.requester.display_avatar)\
                .set_image(url = current_track.thumbnail)\
                \
                .add_field(name=f"{MyEmojis.YOUTUBE_ICON} YT channel" if YT_creator else "💡 Creator",
                            value=Creator)\
                .add_field(name="↔️ Length",
                            value=f'`{convert.length_format(getattr(current_track,"duration"))}`')\
                .add_field(name="📝 Lyrics",
                            value=f"*Available in {len(current_track.subtitles)} languages*" if getattr(current_track,"subtitles",None) else "*Unavailable*")\
                \
                .add_field(name="📶 Volume ",
                            value=f"`{self.volume_percentage}%`")\
                .add_field(name="⏩ Tempo",
                            value=f"`{self.tempo:.2f}`")\
                .add_field(name="ℹ️ Pitch",
                            value=f'`{self.pitch:.2f}`')\
                \
                .add_field(name="🔊 Voice Channel",
                            value=f"{self.guild.voice_client.channel.mention}")\
                .add_field(name="🔂 Looping",
                            value=f'**{convert.bool_to_str(self.looping)}**')\
                .add_field(name="🔁 Queue looping",
                            value=f'**{convert.bool_to_str(self.queue_looping)}**')
        if self.get(1):
            rembed.set_footer(text=f"Next track : {self[1].title}",icon_url=self[1].thumbnail)
        elif self.auto_play and not self.queue_looping:
            rembed.set_footer(text=f"Auto-play : {self.recommend.title}",icon_url=self.recommend.thumbnail)
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
        
        audio_msg : discord.Message = self.audio_message

        if audio_msg: 
            from my_buttons import MusicButtons
            #Apply the changes
            await audio_msg.edit(   embed = self.audio_message_embed,
                                    view = MusicButtons.AudioControllerButtons(self) )
        else:
            logging.warning("Audio message adsent when trying to update it.")

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

        elif isinstance(target,discord.TextChannel):
            self.audio_message = await target.send(**message_info)