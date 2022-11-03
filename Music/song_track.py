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

FRAME_SIZE = Encoder.FRAME_SIZE


RequiredAttr = ("title","webpage_url","duration",
                "thumbnail","channel","uploader","channel_url","uploader_url",
                "subtitles","formats","requester","filesize")

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
        
        data = audioop.mul(data or b"", 2, self.volume)

        if self.audio_filter:
            data = self.audio_filter(data)
        return data

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

    recommendations : Deque[YoutubeVideo]


    def __init__(self,requester:discord.Member,request_message : discord.Message = None,**info:dict):

        self.requester = requester
        self.request_message = request_message
        self.source = None
        self.recommendations = deque([])

        for key,value in info.items():
            if key in RequiredAttr:
                setattr(self,key,value)

        # In fact, every audio can be seekable using my implementation.
        # However i just don't want audio with duarion taking tons of RAM away.
        self.seekable = self.duration < 600
      
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

    @classmethod
    def create_track(cls,query:str,requester:discord.Member,request_message : discord.Message = None) -> Self:
        
        #Some options for extracting the audio from YT
        YDL_OPTION =  {
                        "format": "bestaudio",
                        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
                        # 'restrictfilenames': True,
                        'noplaylist': True,
                        # 'nocheckcertificate': True,
                        # 'ignoreerrors': False,
                        # 'logtostderr': False,
                        "no_color": True,
                        # 'cachedir': "./cache",
                        'quiet': True,
                        'no_warnings': False,
                        'default_search': "url",#'auto',
                        'source_address': '0.0.0.0'
                      }

        with YoutubeDL(YDL_OPTION) as ydl:
            info = ydl.extract_info(query,download=False)

        if 'entries' in info: 
            info = info["entries"][0]  
    
        logging.info("YT-dl extraction successful.")
        return cls(requester,request_message,**info)
    
    def play(self,
            voice_client:discord.VoiceClient,
            after:callable(str)=None,
            volume:float=1,
            pitch:float = 1,
            tempo:float = 1,
        ):

        selected_format : dict = None
        
        #Pick the right format in which we can use ffmpeg on it.
        for fm in self.formats:
            if fm["url"].startswith("https://rr"):
                selected_format = fm
                break
        
        self.src_url   = selected_format["url"]
        self.audio_asr = selected_format["asr"]

        FFMPEG_OPTION = {
            "before_options":"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": f'-vn -af asetrate={self.audio_asr * pitch},aresample={self.audio_asr},atempo={max(round(tempo/pitch,8),0.5)}'
        }
        
        ffmpeg_src = discord.FFmpegPCMAudio(source=self.src_url, **FFMPEG_OPTION)

        src = SeekableAudioSource(seeking =self.seekable, original = ffmpeg_src, volume = volume)

        self.source = src
        voice_client.play(src,after=after)

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