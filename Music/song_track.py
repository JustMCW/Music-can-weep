import discord
import logging
from youtube_dl import YoutubeDL

RequiredAttr = ("title","webpage_url","duration",
                "thumbnail","channel","uploader","channel_url","uploader_url",
                "subtitles","formats","requester")


class SongTrack:

    request_message : discord.Message

    def __init__(self,requester:discord.Member,request_message : discord.Message = None,**info:dict):

        self.requester:discord.Member = requester
        self.request_message = request_message

        for key,value in info.items():
            if key in RequiredAttr:
                setattr(self,key,value)
      
    
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
          
        if 'entries' in info: 
            info = info["entries"][0]  
    

        return cls(requester,request_message,**info)
    
    def play(self,
            voice_client:discord.VoiceClient,
            after:callable(str)=None,
            volume:float=1,
            pitch:float = 1, #slowed
            speed:float = 1,
            position:float=0
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
        
        src_url   = selected_format["url"]
        audio_asr = selected_format["asr"]
        #offset = 1.086378737541528 #1.105 #  0.187 # 0.089 Stupid stuff i have done b4
        print(position)
        FFMPEG_OPTION = {
            "before_options":"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": f'-vn -ss {position} -af asetrate={audio_asr * pitch},aresample={audio_asr},atempo={max(round(speed/pitch,8),0.5)}' # -f:a atempo={speed} atempo={speed * 1/pitch}
        }

        try:
            src = discord.FFmpegPCMAudio(source=src_url, **FFMPEG_OPTION)
        except discord.ClientException as e:
            logging.info(f"{e}, looking for the ffmpeg locally")
            src = discord.FFmpegPCMAudio(executable="./exe/ffmpeg",
                                         source=src_url, **FFMPEG_OPTION)

        vol_src = discord.PCMVolumeTransformer(original = src,
                                                volume = volume)
        logging.info("Successfully Transformed into PCM")
        voice_client.play(vol_src,after=after)
