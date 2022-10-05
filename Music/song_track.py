from typing import Callable,Union
import discord
from discord.utils import MISSING
import logging
from youtube_dl import YoutubeDL
from io import BytesIO,FileIO
from discord.opus import Encoder
FRAME_SIZE = Encoder.FRAME_SIZE


RequiredAttr = ("title","webpage_url","duration",
                "thumbnail","channel","uploader","channel_url","uploader_url",
                "subtitles","formats","requester","filesize")

#just so that we can accesss the return code.
class FFmpegPCMAudio(discord.FFmpegPCMAudio):
    returncode : int = None
    def _kill_process(self) -> None:
        if not self._process is MISSING:
            super()._kill_process()
            self.returncode = self._process.returncode
            
discord.FFmpegPCMAudio = FFmpegPCMAudio

class FileAudioSource(discord.AudioSource):
    frame_counter  : int
    def __init__(self,file):
        self.frame_counter = 0
        self.file = FileIO(file)

    def read(self) -> bytes:
        self.file.seek(FRAME_SIZE * self.frame_counter)
        self.frame_counter += 1
        ret = self.file.read(FRAME_SIZE)
        return ret

    def cleanup(self) -> None:
        self.file.close()

class SeekableAudioSource(discord.PCMVolumeTransformer):
    """PCMVolumeTransformer added with seeking control on top.
    Inhertits every attributes from PCMVolumeTransformer with more attributes for control to audio time position.

    Attributes
    ------------
    frame_counter: :class:`int`
        Manipulate this to seek through the audio.
        One frame is equivalent to 20ms
    _bytes: :class:`BytesIO`
        the audio is stored to achieve seeking.
    """
    audio_filter   : Callable[[bytes],bytes] = None
    frame_counter  : int # Runs every 20ms and determines the position of our audio
    audio_bytes    : BytesIO

    def __init__(self,*args,**kwargs):
        self.frame_counter = 0
        self.audio_bytes = BytesIO()

        super().__init__(*args,**kwargs)


    def read(self) -> bytes:

        self.write_frame()


        self.audio_bytes.seek(FRAME_SIZE * self.frame_counter)
        data = self.audio_bytes.read()

        if not data:
            return super().read()
        else:
            self.frame_counter += 1

        
        return data

        if self.audio_filter:
            return self.audio_filter(data)
        return data

    def write_frame(self) -> None:
        """Write a frame to attribute `audio_bytes`, but doesn't return it"""
        data_read = super().read()
        if data_read:
            self.audio_bytes.write(data_read)


    #We cleaned the original source somewhere else. So we don't have to here
    def cleanup(self) -> None:
        self.audio_bytes.close()


class AutoPlayUser(discord.Member):
    mention = "Auto-play"
    display_name="auto-play"
    display_avatar="https://cdn.discordapp.com/attachments/954810071848742992/1026654075888078878/unknown.png"

class SongTrack:

    request_message : discord.Message
    source          : SeekableAudioSource

    def __init__(self,requester:discord.Member,request_message : discord.Message = None,**info:dict):

        self.requester = requester
        self.request_message = request_message

        for key,value in info.items():
            if key in RequiredAttr:
                setattr(self,key,value)
      
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
    def create_track(cls,query:str,requester:discord.Member,request_message : discord.Message = None)->object:
        
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
        import youtube_dl
        youtube_dl.extractor.YoutubeRecommendedIE
        if 'entries' in info: 
            info = info["entries"][0]  
    

        return cls(requester,request_message,**info)
    
    def play(self,
            voice_client:discord.VoiceClient,
            after:callable(str)=None,
            volume:float=1,
            pitch:float = 1, #slowed
            tempo:float = 1,
        ):
        """
        pitch 1   , speed 1
        pitch 0.5 , speed 2
        higher pitch, higher speed.
        speed = set_speed / set_pitch
        """
        

        selected_format : dict = None
        
        #Pick the right format in which we can use ffmpeg on it.
        for fm in self.formats:
            if fm["url"].startswith("https://rr"):
                selected_format = fm
                break
        
        self.src_url   = selected_format["url"]
        self.audio_asr = selected_format["asr"]
        #offset = 1.086378737541528 #1.105 #  0.187 # 0.089 Stupid stuff i have done b4
        FFMPEG_OPTION = {
            "before_options":"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": f'-vn -af asetrate={self.audio_asr * pitch},aresample={self.audio_asr},atempo={max(round(tempo/pitch,8),0.5)}' # -f:a atempo={speed} atempo={speed * 1/pitch}
        }
        
        try:
            ffmpeg_src = discord.FFmpegPCMAudio(source=self.src_url, **FFMPEG_OPTION)
        except discord.ClientException as e:
            logging.info(f"{e}, looking for the ffmpeg locally")
            ffmpeg_src = discord.FFmpegPCMAudio(executable="./ffmpeg",source=self.src_url, **FFMPEG_OPTION)
        
        vol_src = SeekableAudioSource(original = ffmpeg_src,
                                      volume = volume)

        logging.info("Successfully Transformed into PCM")
        self.source = vol_src
        #import io
        # _stdout:io.BufferedReader = self.source.original._stdout
        # _stdout.read(int(round(discord.opus._OpusStruct.FRAME_SIZE * 50 * position)))
        #['__class__', '__del__', '__delattr__', '__dict__', '__dir__', '__doc__', '__enter__', '__eq__', '__exit__', '__format__', '__ge__', '__getattribute__', '__gt__', '__hash__', '__init__', '__init_subclass__', '__iter__', '__le__', '__lt__', '__ne__', '__new__', '__next__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__', '__str__', '__subclasshook__', '_checkClosed', '_checkReadable', '_checkSeekable', '_checkWritable', '_dealloc_warn', '_finalizing', 'close', 'closed', 'detach', 'fileno', 'flush', 'isatty', 'mode', 'name', 'peek', 'raw', 'read', 'read1', 'readable', 'readinto', 'readinto1', 'readline', 'readlines', 'seek', 'seekable', 'tell', 'truncate', 'writable', 'write', 'writelines']
        
        voice_client.play(vol_src,after=after)
