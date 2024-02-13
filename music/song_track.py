import logging
import audioop
import threading
import requests
import re
import time

from io import BytesIO
from typing import Callable,Tuple,Deque,List,TypedDict,Any,Optional,TYPE_CHECKING
from collections import deque

import discord
from discord.utils import MISSING
from discord.opus  import Encoder

# from youtube_dl import YoutubeDL,utils
# from youtube_dl.extractor import youtube
# from youtube_dl import jsinterp
from yt_dlp import YoutubeDL, utils

from youtube_utils import ( 
    YoutubeVideo,
    get_recommendation,
    url_matcher,
    search_from_youtube,
    get_spotify_track_title,
)


logger = logging.getLogger(__name__)

FRAME_SIZE = Encoder.FRAME_SIZE
DEFAULT_SAMPLE_RATE = 48000
DEFAULT_IMAGES = [
    "https://www.fcnaustin.com/wp-content/uploads/2018/08/Sound.gif",
    "https://i.pinimg.com/originals/07/4d/0f/074d0f0e457470c7d6a8116077d9ab17.gif", 
    "https://media.tenor.com/images/b70f2cee812677e9d7f46fe62155b117/tenor.gif", #https://media.tenor.com/images/b70f2cee812677e9d7f46fe62155b117/tenor.gif
    "https://media.tenor.com/sv9DsEJe-AAAAAAC/vibe-cat.gif",
    "https://media.tenor.com/_yFLs1OWgBAAAAAC/vinyl-disc-dance-music.gif",
    "https://media.tenor.com/JP7kHyaCOEcAAAAM/lel-music.gif",
    # "https://tenor.com/zh-HK/view/pepe-headphones-music-gif-14789865",
    # "https://tenor.com/zh-HK/view/vinyl-disc-dance-music-escutando-musica-dançando-listening-to-music-gif-24958969"
]

from enum import Enum

class TrackDomain(Enum):
    YOUTUBE    = ["youtube","youtu"]
    SOUNDCLOUD = ["soundcloud"]
    SPOTIFY    = ["spotify"]
    DISCORD_ATTACHMENT = ["discordapp"]

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

#Options for the youtube-dl & ffmpeg
YDL_OPTION =  {
    "format": "bestaudio",
    # 'restrictfilenames': True,
    'noplaylist': True,
    # 'nocheckcertificate': True,
    # 'ignoreerrors': False,
    # 'logtostderr': False,
    #"no_cache_dir" : True,
    #"rm_cache_dir" : True, #Links are only avaible for a short period of time, no point of doing cache

    # "no_color": True,
    # 'cachedir': ".",
    'quiet': True,
    'no_warnings': True,
    'default_search': "url",#'auto',
    'source_address': '0.0.0.0'
}

DEFAULT_FFMPEG_OPTION = {
    "before_options" : "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn"
}

ydl = YoutubeDL(YDL_OPTION)

class _FFmpegPCMAudio(discord.FFmpegPCMAudio):
    """This version of ffmpeg pcm audio allows us to obtain the return code of the ffmpeg process
    however cleanup action has to be done. """
    returncode : int = 0

    def _kill_process(self) -> None:
        super()._kill_process()
        if not self._process is MISSING:
            self.returncode = self._process.returncode

    def __del__(self) -> None:
        logger.debug(f"Deleted : {self.__class__.__name__}")

class TimeFrameAudio(discord.PCMVolumeTransformer):
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
        The audio read will be passed to this function then returning it.
        This can be used to change the audio data directly
        
    """
    original       : _FFmpegPCMAudio #We're gonna use this on other audio source
    audio_filter   : Optional[Callable[[bytes],bytes]] = None # I suppose I can do crazy stuff with this in the future, for now tho, it's only for volume controlling
    frame_counter  : int
    _audio_bytes   : BytesIO

    def __init__(self, original: _FFmpegPCMAudio|discord.FFmpegAudio, volume: float = 1, seeking: bool = True):
        self.frame_counter = 0
        self.seekable      = seeking
        if seeking:
            self._audio_bytes   = BytesIO()
        super().__init__(original, volume)

    def read_from_loaded_audio(self) -> bytes:
        self._audio_bytes.seek(FRAME_SIZE * self.frame_counter)
        return self._audio_bytes.read()[:FRAME_SIZE]

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
            self._audio_bytes.write(data_read)
        return data_read

    #We cleaned the original source elsewhere. So we don't have to here
    def cleanup(self) -> None:
        logger.info("Audio thread exited.")
        self._audio_bytes.close()
    
    def __del__(self) -> None:
        if not self.seekable:
            return
        if not self._audio_bytes.closed:
            self._audio_bytes.close()

class LiveStreamAudio(TimeFrameAudio):
    """Streams by constantly requesting data from `source_url`"""
    original : discord.FFmpegPCMAudio
    fragment_index  : int # indicates which audio, we're wokring on
    audio_fragments : List[str]
    current_ffmpeg_audio : discord.FFmpegPCMAudio
    next_ffmpeg_audio : discord.FFmpegPCMAudio # we preload one fragment ahead to avoid loading lag

    def __init__(
        self, 
        source_url : str, 
        volume     : float = 1, 
        ffmpeg_options : dict = DEFAULT_FFMPEG_OPTION,
    ):
        self.volume      = volume
        self.fragment_index = 0

        self._src_url  = source_url
        self._ffmpeg_options = ffmpeg_options

        self.collect_audio_fragments()

        super().__init__(
            original=self.current_ffmpeg_audio,
            volume =volume,
            seeking=False,
        )

    def collect_audio_fragments(self):
        """
        read 30 seconds total worth of audio from the source url, 
        as 6 fragments with each of them being 5 seconds long
        and set it to `self.audio_fragments`
        """
        response = requests.get(self._src_url)
        content = response.content.decode("utf-8")

        # Extract audio from the the urls
        urls = re.findall(r"https://.+seg\.ts",content)
        self.audio_fragments = urls

        self.fragment_index = 0
        self.current_ffmpeg_audio = discord.FFmpegPCMAudio(source=self.audio_fragments[self.fragment_index], **self._ffmpeg_options)
        self.next_ffmpeg_audio = discord.FFmpegPCMAudio(source=self.audio_fragments[self.fragment_index + 1], **self._ffmpeg_options)

    def load_next_frag(self):
        self.next_ffmpeg_audio = discord.FFmpegPCMAudio(source=self.audio_fragments[self.fragment_index], **self._ffmpeg_options)
        self.fragment_index += 1

    def read(self) -> bytes:
        
        data = super().read()

        if data:
            return data
            
        # Reached the end of the this fragment group
        if self.fragment_index >= len(self.audio_fragments):
            self.collect_audio_fragments() 
            logger.info("Moving on to the next fragment.")

        # Otherwise it's just the end of the current fragment, load up the next one.
        self.current_ffmpeg_audio.cleanup()
        self.current_ffmpeg_audio = self.next_ffmpeg_audio

        # Preload the next fragment
        threading.Thread(self.load_next_frag()).start()
        
        self.original = self.current_ffmpeg_audio
        return self.original.read()

    def cleanup(self) -> None:
        self.current_ffmpeg_audio.cleanup()
        self.next_ffmpeg_audio.cleanup()


AudioSource = TimeFrameAudio|LiveStreamAudio

class AutoPlayUser(discord.Member):
    def __init__(self):
        pass
    mention = "Auto-play" #type: ignore
    display_name ="auto-play" #type: ignore
    display_avatar= "https://cdn.discordapp.com/attachments/954810071848742992/1026654075888078878/unknown.png" #type: ignore

autoplay_user = AutoPlayUser()

class SongTrack:
    """Base audio sound track"""
    title = "title"
    duration = 0
    thumbnail = ""

    # The url displayed on the embed
    webpage_url = ""
    # This must be defined before calling `SongTrack.play`
    source_url  = ""  

    sample_rate     : int
    request_message : discord.Message | None
    source          : TimeFrameAudio | LiveStreamAudio

    def __init__(
        self,
        title: str,
        duration: int,
        thumbnail: str,
        webpage_url : str,
        source_url: str,
        requester: discord.Member = autoplay_user,
        request_message : discord.Message | None = None, 
        seekable = True
    ):
        self.title = title
        self.duration = duration

        # if thumbnail:
        self.thumbnail = thumbnail

        self.webpage_url = webpage_url
        self.source_url = source_url
        
        self.requester = requester
        self.request_message = request_message

        self.sample_rate = 0

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

    def get_source(self, volume, ffmpeg_option) -> TimeFrameAudio:
        return TimeFrameAudio(
            original = _FFmpegPCMAudio(
                source=self.source_url, 
                **ffmpeg_option
            ), 
            volume = volume,
            seeking = self.seekable, 
        )

    def play(
        self,
        voice_client: discord.VoiceClient,
        after: Optional[Callable[[Exception|None], Any]]= None,
        volume: float=1,
        pitch: float = 1,
        tempo: float = 1,
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
        
        # maybe we let the stream initialise first ?
        # voice_client.ws.speak()
        time.sleep(1)
        voice_client.play(self.source,after=after)
        return

    def to_dict(self) -> dict:
        """Determinds how the track is going to be stored in a database"""
        raise NotImplementedError


class WebFileTrack(SongTrack):
    """For any audio file on the internet, using ffmpeg"""
    file_format : str
    file_size   : int # in bytes

    def __init__(
        self, 
        title: str, 
        source_url: str, 
        file_format: str,
        file_size : int,

        duration: int = 0, 
        # we are likely to not have a thumbnail
        thumbnail: Optional[str] = None, 
        requester: discord.Member = autoplay_user, 
        request_message: Optional[discord.Message] = None, 
        seekable=True
    ):

        self.file_format = file_format
        self.file_size   = file_size

        from random import choice

        super().__init__(
            title=title, 
            duration=duration, 
            thumbnail=thumbnail or choice(DEFAULT_IMAGES), 
            webpage_url=source_url,  # we dont have a webpage
            source_url =source_url, 
            requester=requester, 
            request_message=request_message, 
            seekable=seekable
        )

        # if not self.thumbnail:
        #     @property
        #     def random_thumbnail(self):
        #         from random import choice
        #         img = choice(DEFAULT_IMAGES)
        #         logger.warning(img)
        #         return img
        #     self.thumbnail = random_thumbnail
        #     print(self.thumbnail)

    def to_dict(self) -> dict:
        return {
            "title" : self.title,
            "url" : self.source_url,
            "thumbnail": self.thumbnail,
        }

class UnknownSourceFileTrack(WebFileTrack):
    """For audio from unknown domain"""
    def __init__(self,source_url : str, *args,**kwargs):
        super().__init__(
            title="Unknown",
            source_url=source_url,
            file_format="Unknown",
            file_size=0,
            *args,**kwargs
        )

class DiscordFileTrack(WebFileTrack):
    """Song track for a discord attachment"""

    def __init__(
        self, 
        url: str,
        *args,
        **kwargs, 
    ):
        match = url_matcher(url)

        if not match:
            raise ValueError

        # The following implementation is only for discord attachments
        if match["domain"] != TrackDomain.DISCORD_ATTACHMENT.value[0]:
            return 

        headers = requests.head(url).headers

        #type checl : ignore
        search = re.search(
            r"filename=(.+)\.(.+)\Z",
            headers["Content-Disposition"]
        )
        if not search:
            raise utils.UnavailableVideoError()
        
        file_name, extension = search.groups()

        super().__init__(
            title= file_name,
            source_url=url,
            file_size  = int(headers["Content-Length"]),
            file_format= headers["Content-Type"] or extension,
 
            seekable=True,
            *args,
            **kwargs,
        )
        

class WebsiteSongTrack(SongTrack):
    """Apply yt-dl then ffmpeg"""
    info : youtube_dl_info
    webpage_url  : str
    uploader     : Tuple[str,str]

    def __init__(self, url, *args, **kwargs):
        
        # with YoutubeDL(YDL_OPTION) as ydl:
                   
        info : youtube_dl_info = ydl.extract_info(url,download=False,process=False) # type: ignore
        logger.debug("YT-dl extraction successful.")

        self.info = info
        audio_format = info["formats"][0]


        if info["duration"] is not None:
            for fm in info["formats"]:
                if fm.get("asr",0) == DEFAULT_SAMPLE_RATE or fm.get("asr",0) == 44100:
                    audio_format = info["formats"] = fm
                    break

        super().__init__(
            info["title"], 
            info["duration"], 
            info.get("thumbnail",info["thumbnails"][-1]["url"]), 
            info["webpage_url"],
            audio_format["url"] if (not audio_format["url"].startswith("https://manifest") or not info["duration"]) else  audio_format["fragment_base_url"], 
            *args, **kwargs
        )

        self.webpage_url = info["webpage_url"]
        self.uploader = (info["uploader"],info["uploader_url"])
        self.sample_rate = audio_format.get("asr")
        self.subtitles = info.get("subtitles")

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
    """A youtube video track, can be a live stream"""
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
        self.is_live = self.info["duration"] is None



    def get_source(self, volume, ffmpeg_option) -> 'AudioSource':
        if self.is_live:
            return LiveStreamAudio(
                self.source_url,
                volume,
                ffmpeg_option
            )
        else:
            return super().get_source(volume, ffmpeg_option)

    def _generate_rec(self):
        """generates the recommendation of this track"""
        from random import randint
        rec = None
        while not rec:
            rec = get_recommendation(self.webpage_url)
        self.recommendations = deque(rec)
        self.recommendations.rotate(-1 * randint(0,1))

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

class SpotifyTrack(YoutubeTrack):
    """This is one is an imposter, it just obtains the title and search it on youtube LOL"""
    def __init__(self, spotify_url, title=None, *args, **kwargs):
        title = title or get_spotify_track_title(spotify_url)
        url = search_from_youtube(title,1)[0].url
        super().__init__(url, *args, **kwargs)




# Finding the corrosponding track type for each Domain
DOMAIN_TO_TRACK = {
    TrackDomain.YOUTUBE:YoutubeTrack,
    TrackDomain.SOUNDCLOUD:SoundcloudTrack,
    TrackDomain.SPOTIFY:SpotifyTrack,
    TrackDomain.DISCORD_ATTACHMENT:DiscordFileTrack,
}

def create_track_from_url(
    url : str, 
    requester: discord.Member | discord.User = autoplay_user, 
    request_message: discord.Message | None = None
) -> SongTrack:

    kwargs = {
        "requester":requester,
        "request_message":request_message
    }

    match = url_matcher(url)
    if not match: raise ValueError("Your url is invalid bro.")
    url_domain = match["domain"]

    for domain, track_type in DOMAIN_TO_TRACK.items():
        if url_domain in domain.value:
            logger.info(f"Track domain : {domain.value[0]} | Track type : {track_type.__name__}")
            return track_type(url,**kwargs)

    try:
        return WebsiteSongTrack(url,**kwargs)
    except KeyError:
        return UnknownSourceFileTrack(url,**kwargs)
        