import discord
from youtube_dl import YoutubeDL

RequiredAttr = ["title","webpage_url","duration",
                "thumbnail","channel","channel_url",
                "subtitles","formats"]


class SongTrack:
    def __init__(self,requester:discord.Member,**info):

      self._requester = requester
      
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

        audio_source = discord.PCMVolumeTransformer(original = discord.FFmpegPCMAudio(#executable="/Users/xwong/Documents/Daily/Learning/Computing/exe/ffmpeg",
                                                                                      source=self.formats[0].get("url"), **FFMPEG_OPTION),
                                                    volume = volume)

        voice_client.play(audio_source,after=after)
    
    @property
    def requester(self):
        return self._requester
