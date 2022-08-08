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
        pitch 1 + offset , speed 1
        pitch 0.5 + offset, speed 2
        higher pitch, higher speed.
        """
        offset = 1.086378737541528 #1.105 #  0.187 # 0.089
        FFMPEG_OPTION ={ #0.09 SUPER TINY FASTER
                        "before_options":"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                        "options": f'-vn -ss {position} -af asetrate={44100 * pitch * offset},aresample=44100,atempo={max(round(speed/pitch,8),0.5)}' # -f:a atempo={speed} atempo={speed * 1/pitch}
                       }


        
        src_url:str = self.formats[0].get("url")
        
        if src_url.startswith("https://manifest.googlevideo.com"):
            logging.info("Is fragment url")
            try:
                src_url = self.formats[0]["fragment_base_url"]
            except KeyError:
                logging.WARNING(src_url)

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
    

