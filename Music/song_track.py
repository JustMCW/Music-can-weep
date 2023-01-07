import logging
from io import BytesIO
from typing import Callable,Tuple,Deque,List,TypedDict,Any,Union  
from typing_extensions import Self

import discord
from discord.utils import MISSING
from discord.opus  import Encoder

from collections import deque
from youtube_dl import YoutubeDL
from youtube_utils import ( 
    YoutubeVideo,
    get_recommendation,
    url_matcher,
    search_from_youtube,
    get_spotify_track_title,
)

import json
import audioop

# for live streaming
import threading
import re
import requests

logger = logging.getLogger(__name__)

FRAME_SIZE = Encoder.FRAME_SIZE
DEFAULT_SAMPLE_RATE = 48000

from enum import Enum

class TrackDomain(Enum):
    YOUTUBE    = "youtube"
    SOUNDCLOUD = "soundcloud"
    SPOTIFY    = "spotify"
    DISCORD_ATTACHMENT = "discordapp"

class youtube_dl_info(TypedDict):
    id: str
    title: str
    formats: list
    thumbnails: list
    description: str
    upload_date: str
    uploader: str
    uploader_id: str
    uploader_url: str
    channel_id: str
    channel_url: str
    duration: int
    view_count: int
    average_rating: Any
    age_limit: int
    webpage_url: str
    categories: list
    tags: list
    is_live: Any
    automatic_captions: dict
    subtitles: dict
    chapters: list
    channel: str
    extractor: str
    webpage_url_basename: str
    extractor_key: str
    playlist: Any
    playlist_index: Any
    thumbnail: str
    display_id: str
    requested_subtitles: Any
    requested_formats: tuple
    format: str
    format_id: str
    width: int
    height: int
    resolution: Any
    fps: int
    vcodec: str
    vbr: float
    stretched_ratio: Any
    acodec: str
    abr: float
    ext: str

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

DEFAULT_FFMPEG_OPTION = {
    "before_options" : "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn"
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
        super()._kill_process()
        if not self._process is MISSING:
            self.returncode = self._process.returncode

    def __del__(self) -> None:
        logger.debug(f"Deleted : {self.__class__.__name__}")

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
        logger.info("Audio thread exited.")
        self.audio_bytes.close()
    
    def __del__(self) -> None:
        if not self.audio_bytes.closed:
            self.audio_bytes.close()

class LiveStreamAudioSource(discord.PCMVolumeTransformer):
    """
    
    """
    source_url      : str
    audio_fragments : List[discord.FFmpegPCMAudio]
    audio_index     : int # indicates which audio, we're wokring on

    def __init__(
        self, 
        source_url : str, 
        volume     : float = 1, 
        ffmpeg_options : dict = DEFAULT_FFMPEG_OPTION,
    ):
        self.source_url  = source_url
        self.volume      = volume
        self.audio_index = 0 
        self.ffmpeg_options = ffmpeg_options

        self.collect_audio_fragments()

    def collect_audio_fragments(self):
        """
        read 30 seconds total worth of audio from the source url, 
        as 6 fragments with each of them being 5 seconds long
        and set it to `self.audios`
        """
        response = requests.get(self.source_url)
        content = response.content.decode("utf-8")

        # Extract audio from the the urls
        urls = re.findall(r"https://.+seg\.ts",content)
        self.audio_fragments = [
            discord.FFmpegPCMAudio(source=url, **self.ffmpeg_options)
            for url in urls
        ]

    def read(self) -> bytes:
        data = self.audio_fragments[self.audio_index].read()

        # Moving on to the next fragment
        if not data:

            self.audio_fragments[self.audio_index].cleanup()
            self.audio_index += 1

            # reached the end of the current fragment 
            if self.audio_index == len(self.audio_fragments):
                self.next_fragment()

            return self.read()

        # Modify Volume
        return audioop.mul(data, 2, min(self.volume, 2.0))

    def next_fragment(self):
        logger.info("Next fragment")
        self.cleanup()
        self.audio_index = 0
        self.collect_audio_fragments() 

    def cleanup(self) -> None:
        for src in self.audio_fragments:
            src.cleanup()

class AutoPlayUser(discord.Member):
    mention = "Auto-play"
    display_name="auto-play"
    display_avatar="https://cdn.discordapp.com/attachments/954810071848742992/1026654075888078878/unknown.png"

class SongTrack:
    title = "title"
    duration = 0
    thumbnail = ""

    # The url displayed on the embed
    webpage_url = ""
    # This must be defined before calling `SongTrack.play`
    source_url  = ""  

    sample_rate     : int
    request_message : discord.Message
    source          : Union[SeekableAudioSource,LiveStreamAudioSource] = None

    def __init__(
        self,
        title: str,
        duration: int,
        thumbnail: str,
        webpage_url : str,
        source_url: str,
        requester:discord.Member = AutoPlayUser,
        request_message : discord.Message = None, 
        seekable = True
    ):
        self.title = title
        self.duration = duration
        self.thumbnail = thumbnail

        self.webpage_url = webpage_url
        self.source_url = source_url
        
        self.requester = requester
        self.request_message = request_message

        self.sample_rate = None
        self.source = None

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

    def get_source(self, volume, ffmpeg_option) -> SeekableAudioSource:
        return SeekableAudioSource(
            seeking = self.seekable, 
            original = discord.FFmpegPCMAudio(
                source=self.source_url, 
                **ffmpeg_option
            ), 
            volume = volume
        )

    def play(self,
            voice_client:discord.VoiceClient,
            after :callable(str)=None,
            volume :float=1,
            pitch  :float = 1,
            tempo  :float = 1,
            force_apply = True # if true, the sample rate will be set to 48000 if it's unkwown
        ):
        if not self.source_url:
            return logger.error("Source url not defined")
   
        ffmpeg_option = DEFAULT_FFMPEG_OPTION.copy()
            
        # Modifying pitch & tempo, by applying ffmpeg options

        if pitch != 1 or tempo != 1:
            sample_rate = self.sample_rate
            if not sample_rate and force_apply:
                logger.info("Forcing the sample rate to be 48000")
                sample_rate = DEFAULT_SAMPLE_RATE

            if sample_rate is not None:
                ffmpeg_option["options"] += f' -af asetrate={sample_rate * pitch},aresample={sample_rate},atempo={max(round(tempo/pitch,8),0.5)}'
            else:
                logger.info("Audio sample rate is undefined.")

        logger.info(f"FFMPEG option : {ffmpeg_option}")
        self.source = self.get_source(volume,ffmpeg_option)
        voice_client.play(self.source,after=after)
        return

    def to_dict(self) -> dict:
        """Determinds how the track is going to be stored in a database"""
        raise NotImplementedError

class WebsiteSongTrack(SongTrack):
    info : youtube_dl_info
    webpage_url  : str
    uploader     : Tuple[str,str]

    def __init__(self, url, *args, **kwargs):
        
        with YoutubeDL(YDL_OPTION) as ydl:
            info : youtube_dl_info = ydl.extract_info(url,download=False,process=False)
        logger.debug("YT-dl extraction successful.")

        self.info = info
        audio_format = info["formats"][0]
        
        if not info["is_live"]:
            for fm in info["formats"]:
                if fm["asr"] == DEFAULT_SAMPLE_RATE or fm["asr"] == 44100:
                    audio_format = info["formats"] = fm
                    break

            # r = requests.get(audio_format["url"])
            # data = r.text.replace("</BaseURL>","\n").replace("<BaseURL>","\n")
            # urls = re.findall("(https://.+)",data)
            # audio_format["url"] = audio_format["fragment_base_url"]

        super().__init__(
            info["title"], 
            info["duration"], 
            info.get("thumbnail",info["thumbnails"][-1]["url"]), 
            info["webpage_url"],
            audio_format["url"] if (not audio_format["url"].startswith("https://manifest") or info["is_live"]) else  audio_format["fragment_base_url"], 
            *args, **kwargs
        )
        self.webpage_url = info["webpage_url"]
        self.uploader = (info["uploader"],info["uploader_url"])
        self.sample_rate = audio_format.get("asr")

    def to_dict(self) -> dict:
        return {
            "title" : self.title,
            "uploader" : self.uploader[0],
            "uploader_url" : self.uploader[1],
            "url" : self.webpage_url,
            "duration" : self.duration,
            "thumbnail": self.thumbnail,
        }

class YoutubeTrack(WebsiteSongTrack):
    recommendations : Deque[YoutubeVideo]
    channel : Tuple[str,str]
    is_live : bool

    def __init__(
        self, 
        url : str, 
        *args, **kwargs
    ):
        super().__init__(url, *args, **kwargs)
        self.recommendations = deque([])
        self.channel = (self.info["channel"],self.info["channel_url"])
        self.is_live = bool(self.info["is_live"])


    def get_source(self, volume, ffmpeg_option) -> Union[SeekableAudioSource, LiveStreamAudioSource]:
        if self.is_live:
            return LiveStreamAudioSource(
                self.source_url,
                volume,
                ffmpeg_option
            )
        else:
            return super().get_source(volume, ffmpeg_option)

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
        except (IndexError, KeyError):
            self._generate_rec()
            return self.recommendations[0]

    def to_dict(self) -> dict:
        return {
            "title" : self.title,
            "channel" : self.channel[0],
            "channel_url" : self.channel[1],
            "url" : self.webpage_url,
            "duration" : self.duration,
            "thumbnail": self.thumbnail,
        }

class SoundcloudTrack(WebsiteSongTrack):
    pass

class SpotifyTrack(WebsiteSongTrack):
    def __init__(self, spotify_url, *args, **kwargs):
        title = get_spotify_track_title(spotify_url)
        url = search_from_youtube(title,1)[0].url
        super().__init__(url, *args, **kwargs)

class WebFileTrack(SongTrack):
    file_format : str
    file_size   : int # in bytes
    
    def __init__(
        self, 
        title: str, 
        source_url: str, 
        file_format: str,
        file_size : int,

        duration: int = None, 
        # we are likely to not have a thumbnail
        thumbnail: str = "https://tse2.mm.bing.net/th?id=OIP.9hREDpFDH5QAwXMBfrD2yQHaHa&pid=Api", 
        requester: discord.Member = AutoPlayUser, 
        request_message: discord.Message = None, 
        seekable=True
    ):
        self.file_format = file_format
        self.file_size   = file_size
        super().__init__(
            title=title, 
            duration=duration, 
            thumbnail=thumbnail, 
            webpage_url=source_url,  # we dont have a webpage
            source_url =source_url, 
            requester=requester, 
            request_message=request_message, 
            seekable=seekable
        )

    def to_dict(self) -> dict:
        return {
            "title" : self.title,
            "url" : self.source_url,
            "thumbnail": self.thumbnail,
        }

class UnknownSourceFileTrack(WebFileTrack):
    def __init__(self,source_url : str, *args,**kwargs):
        super().__init__(
            title="Unknown",
            source_url=source_url,
            file_format="Unknown",
            file_size="Unknown",
            *args,**kwargs)

class DiscordFileTrack(WebFileTrack):
    def __init__(
        self, 
        url: str,
        requester: discord.Member, 
        request_message: discord.Message = None, 
    ):

        # The following implementation is only for discord attachments
        if url_matcher(url)["domain"] != TrackDomain.DISCORD_ATTACHMENT.value:
            return 

        headers = requests.head(url).headers

        file_name, extension = re.search(
            r"filename=(.+)\.(.+)\Z",
            headers["Content-Disposition"]
        ).groups()

        super().__init__(
            title= file_name,
            source_url=url,
            file_size  =headers["Content-Length"],
            file_format=headers["Content-Type"] or extension,

            requester=requester, 
            request_message=request_message, 
            seekable=False
        )
        

DOMAIN_TRACK_TYPE = {
    TrackDomain.YOUTUBE:YoutubeTrack,
    TrackDomain.SOUNDCLOUD:SoundcloudTrack,
    TrackDomain.SPOTIFY:SpotifyTrack,
    TrackDomain.DISCORD_ATTACHMENT:DiscordFileTrack,
}

def create_track_from_url(
    url : str, 
    requester: discord.Member = AutoPlayUser, 
    request_message: discord.Message = None
) -> SongTrack:

    kwargs = {
        "requester":requester,
        "request_message":request_message
    }
    
    matches = url_matcher(url)
    if not matches:
        raise ValueError(f"{url} is not a valid URL")

    for domain, track_type in DOMAIN_TRACK_TYPE.items():
        if domain.value == matches["domain"]:
            logger.info(f"Track domain : {domain.value} | Track type : {track_type.__name__}")
            return track_type(url,**kwargs)

    try:
        return WebsiteSongTrack(url,**kwargs)
    except KeyError:
        return UnknownSourceFileTrack(url,**kwargs)