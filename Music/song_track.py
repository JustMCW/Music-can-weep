import logging
from io import BytesIO
from typing import Callable,Deque
from typing_extensions import Self

import discord
from discord.utils import MISSING
from discord.opus  import Encoder

from collections import deque
from youtube_dl import YoutubeDL
from youtube_utils    import YoutubeVideo,get_recommendation

import audioop

# for live streaming
import threading
import re
import requests

FRAME_SIZE = Encoder.FRAME_SIZE

#Some options for extracting the audio from YT
YDL_OPTION =  {
                "format": "bestaudio",
                # 'restrictfilenames': True,
                'noplaylist': True,
                # 'nocheckcertificate': True,
                # 'ignoreerrors': False,
                # 'logtostderr': False,
                "no_cache_dir" : True,
                "rm_cache_dir" : True, #Links are only avaible for a short period of time, no point of doing cache

                "no_color": True,
                # 'cachedir': "./cache",
                'quiet': True,
                'no_warnings': False,
                'default_search': "url",#'auto',
                'source_address': '0.0.0.0'
                }

class RawBytesAudioSource(discord.AudioSource):
    """This audio source reads from a bytes that has been pre-defined"""
    def __init__(self,b : bytes) -> None:
        self.cache = BytesIO(b)

    def read(self) -> bytes:
        return self.cache.read(Encoder.FRAME_SIZE)

    def cleanup(self) -> None:
        self.cache.close()

#just so that we can accesss the return code.
class FFmpegPCMAudio(discord.FFmpegPCMAudio):
    returncode : int = None
    def _kill_process(self) -> None:
        logging.info("-------------Kill process-----------------")
        super()._kill_process()
        if not self._process is MISSING:
            self.returncode = self._process.returncode

    def __del__(self) -> None:
        logging.info(f"Deleted : {self.__class__.__name__}")

discord.FFmpegPCMAudio = FFmpegPCMAudio

class FileAudioSource(discord.FFmpegPCMAudio):
    def __init__(self, source, *, executable: str = 'ffmpeg', pipe: bool = False, stderr = None, before_options: str = None, options: str = None) -> None:
        if options:
            options += "acodec copy"
        super().__init__(   source, 
                            executable=executable, 
                            pipe=pipe, 
                            stderr=stderr, 
                            before_options=before_options, 
                            options=options)


class SeekableAudioSource(discord.PCMVolumeTransformer):
    """PCMVolumeTransformer added with seeking control on top.
    Inhertits every attributes from PCMVolumeTransformer with more attributes for control to audio time position.

    Seeking is achieved by storing bytes read from the ffmpeg stream, and reading from the stored bytes, which is seekable.

    Attributes
    ------------
    frame_counter: :class:`int`
        Manipulate this to seek through the audio.
        One frame is equivalent to 20ms
    audio_bytes: :class:`BytesIO`
        The audio read from the ffmepg is stored in this attribute.

    audio_filter: :class:`Callable[[bytes],bytes]`
        The audio read will be passed to this function then returning it
        This can be used to change the audio data directly
        
    """
    original       : discord.FFmpegPCMAudio #We're gonna use this on other audio source
    audio_filter   : Callable[[bytes],bytes] = None # I suppose I can do crazy stuff with this in the future, for now tho, it's only for volume controlling
    frame_counter  : int
    audio_bytes    : BytesIO

    def __init__(self,seeking : bool,*args,**kwargs):
        self.frame_counter = 0
        self.seekable = seeking
        self.audio_bytes = BytesIO()
        super().__init__(*args,**kwargs)

    def read_from_loaded_audio(self) -> bytes:
        self.audio_bytes.seek(FRAME_SIZE * self.frame_counter)
        return self.audio_bytes.read()[:FRAME_SIZE]

    def read(self) -> bytes:
        if self.seekable:
            w = self.write_frame()
            data = self.read_from_loaded_audio() or w
        else:
            data = self.original.read()
        self.frame_counter += 1

        if not data:
            return b""

        if self.audio_filter:
            data = self.audio_filter(data)
        return audioop.mul(data, 2, self.volume)

    def write_frame(self) -> bytes:
        """Write a frame of ffmpeg stream bytes to `audio_bytes`"""
        data_read = self.original.read()
        if data_read and self.seekable:
            self.audio_bytes.write(data_read)
            return data_read

    #We cleaned the original source elsewhere. So we don't have to here
    def cleanup(self) -> None:
        logging.info("Audio thread exited.")
        self.audio_bytes.close()
    
    def __del__(self) -> None:
        if not self.audio_bytes.closed:
            self.audio_bytes.close()

class AutoPlayUser(discord.Member):
    mention = "Auto-play"
    display_name="auto-play"
    display_avatar="https://cdn.discordapp.com/attachments/954810071848742992/1026654075888078878/unknown.png"

class SongTrack:
    request_message : discord.Message
    source          : SeekableAudioSource
    # we have a completely different implentation for live streams
    is_livestream   : bool 
    time_lapse_frame = 0

    recommendations : Deque[YoutubeVideo]

    # Defaults
    title = "Track title"
    duration = 0
    thumbnail = "https://tse2.mm.bing.net/th?id=OIP.9hREDpFDH5QAwXMBfrD2yQHaHa&pid=Api"
    webpage_url = "https://www.youtube.com"
    source_url = "" # This must be defined before calling `SongTrack.play``


    def __init__(self,requester:discord.Member = AutoPlayUser,request_message : discord.Message = None, seekable = True):
        
        self.requester = requester
        self.request_message = request_message
        self.source = None
        self.recommendations = deque([])

        # In fact, every audio can be seekable using my implementation.
        # However i just don't want audio with long duarion taking tons of RAM away.
        self.seekable = seekable
      
    @property
    def time_position(self):
        """returns the real time position, ignoring the speed factor"""
        return self.source.frame_counter / 50

    @time_position.setter
    def time_position(self,sec : float):
        self.source.frame_counter = int(max(sec * 50,0))

    @property
    def volume(self):
        return self.source.volume

    @volume.setter
    def volume(self,new_vol : float):
        self.source.volume = new_vol

    def recreate_source_url(self, failure : bool=False):
        """Regenerate the source url for the song track, this is bulit for the 403 http error"""
        #Pick the right format in which we can use ffmpeg on it.
        if failure:
            with YoutubeDL(YDL_OPTION) as ydl:
                info = ydl.extract_info(self.webpage_url,download=False,process=False )
                self.formats = info["formats"]

        selected_format = None
        for fm in self.formats:
            if fm["url"].startswith("https://rr"):
                selected_format = fm
                break
        selected_format = selected_format or self.formats[0]

        if failure and self.source_url == selected_format["url"]:
            logging.warning("Failure of recreation, repeated...")
            return self.recreate_source_url(failure)

        self.source_url   = selected_format["url"]
        self.audio_asr    = selected_format.get("asr",48000)

    @classmethod
    def create_track(cls,query:str,requester:discord.Member,request_message : discord.Message = None) -> Self:

        with YoutubeDL(YDL_OPTION) as ydl:
            info = ydl.extract_info(query,download=False,process=False)

        if 'entries' in info: 
            info = info["entries"][0]  
    
        logging.info("YT-dl extraction successful.")
        track = cls(requester,request_message, seekable = info["duration"] < 600)

        yt_src_attrs = ("title","webpage_url","duration","thumbnails",
                        "channel","channel_url",
                        "uploader","uploader_url",
                        "subtitles","formats")

        for key,value in info.items():
            if key in yt_src_attrs:
                setattr(track,key,value)
        
        # configuring 
        track.thumbnail = track.thumbnails[-1]["url"]

        track.is_livestream = track.duration == 0
        if track.is_livestream:
            track.seekable = False

        track.recreate_source_url()

        return track
    
    @classmethod
    def from_attachment(cls, attachment : discord.Attachment, requester : discord.Member):
        track = cls(requester,seekable=False)
        
        track.title = attachment.filename
        track.webpage_url = attachment.url
        track.source_url = attachment.proxy_url

        return track

    def play(self,
            voice_client:discord.VoiceClient,
            after:callable(str)=None,
            volume:float=1,
            pitch:float = 1,
            tempo:float = 1,
        ):
        if not self.source_url:
            return logging.error("Source url not defined")

        FFMPEG_OPTION = {
            "before_options" : "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn"
        }
        
        if getattr(self,"audio_asr",None):
            FFMPEG_OPTION["options"] += f' -af asetrate={self.audio_asr * pitch},aresample={self.audio_asr},atempo={max(round(tempo/pitch,8),0.5)}'
        else:
            logging.info("Cannot modify pitch and speed if audio sample rate is not defined.")

        if not self.is_livestream:
            src = SeekableAudioSource(
                seeking = self.seekable, 
                original = discord.FFmpegPCMAudio(source=self.source_url, **FFMPEG_OPTION), 
                volume = volume
            )

            self.source = src
            voice_client.play(src,after=after)

        else:

            #we play live here
            print("LIVE")

            ready = threading.Event()
            end   = threading.Event()

            class TimeLaspeFPA(discord.FFmpegPCMAudio):
                def read(_) -> bytes:
                    self.time_lapse_frame += 1
                    return super().read()

            def stream() -> None:

                response = requests.get(self.source_url)
                content = response.content.decode("utf-8")
                
                # Extract the urls
                urls = re.findall(r"https://.+seg\.ts",content)
                audios = [
                    discord.PCMVolumeTransformer(
                        TimeLaspeFPA(source=url, **FFMPEG_OPTION),
                        volume = volume
                    ) 
                    for url in urls
                ]
                
                def playnext(index):
                    # Not the first audio
                    if self.source:
                        self.source.cleanup()
                        # Stopped
                        if self.source.original.returncode == -9:
                            end.set()
                            return ready.set()

                    # Last file
                    if index >= len(audios):
                        ready.set()
                        return 

                    audio = audios[index]
                    self.source = audio
                    voice_client.play(
                        audio,
                        after = lambda _: playnext(index+1)
                    )
                
                playnext(0)

                # every 30 seconds ?
                ready.wait(60)
                ready.clear()

                if voice_client.is_connected() and not end.is_set():
                    stream()
                else:
                    after()
            
            threading.Thread(target=stream).start()

    def _generate_rec(self):
        """generates the recommendation of this track"""
        rec = None
        while not rec:
            rec = get_recommendation(self.webpage_url)
        self.recommendations = deque(rec)

    @property
    def recommend(self) -> YoutubeVideo:
        try:
            return self.recommendations[0]
        except IndexError:
            self._generate_rec()
            return self.recommendations[0]