import discord
from youtube_dl import YoutubeDL

RequiredAttr = ("title","webpage_url","duration",
                "thumbnail","channel","channel_url",
                "subtitles","formats","requester")


class SongTrack:

    __slots__ = RequiredAttr

    def __init__(self,requester:discord.Member,**info:dict):

      self.requester = requester
      
      for key,value in info.items():
          if key in RequiredAttr:
              setattr(self,key,value)
      
    
    @classmethod
    def create_track(cls,query:str,requester:discord.Member)->object:
        
        #Some options for extracting the audio from YT
        YDL_OPTION = {
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
            
        return cls(requester,**info)
    
    def play(self,
            voice_client,
            after:callable(str)=None,
            volume=1,
            position:float=0):
      
        FFMPEG_OPTION = {
          "before_options":"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
          "options": f"-vn -ss {position}"
        }
        #
        src_url = self.formats[0].get("url")
        
        if src_url.startswith("https://manifest.googlevideo.com"):
            print("is fragment url")
            src_url = self.formats[0]["fragment_base_url"]

        try:
            src = discord.FFmpegPCMAudio(source=src_url, **FFMPEG_OPTION)
        except discord.ClientException as e:
            print(e,"So imma look for the ffmpeg locally")
            src = discord.FFmpegPCMAudio(executable="/Users/xwong/Documents/Daily/Learning/Computing/exe/ffmpeg",
                                         source=src_url, **FFMPEG_OPTION)

        vol_src = discord.PCMVolumeTransformer(original = src,
                                                volume = volume)

        voice_client.play(vol_src,after=after)
