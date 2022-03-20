import discord
from main import BOT_INFO

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
    # 'cachedir': True,
    'quiet': True,
    'no_warnings': False,
    'default_search': "url",#'auto',
    'source_address': '0.0.0.0'
}

class SongTrack:
  def __init__(self,**info):

    RequiredAttr = [
      "title","webpage_url","duration",
      "thumbnail","channel","channel_url",
      "subtitles","formats",
    ]
    
    for key,value in info.items():
      if key in RequiredAttr:
        setattr(self,key,value)
  
  @classmethod
  def create_track(cls,query:str)->object:
    from youtube_dl import YoutubeDL
    with YoutubeDL(YDL_OPTION) as ydl:
      info = ydl.extract_info(query, download=False)
      
      if 'entries' in info: 
        info = info["entries"][0]
        
      return cls(**info)
  
  def play(self,
           voice_client,
           after=None,
           volume:float=BOT_INFO.InitialVolume,
           position:float=0):
    
      FFMPEG_OPTION = {
        "before_options":"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": f"-vn -ss {position}"
      }
    
      #Converting the format
      source = discord.FFmpegPCMAudio(self.formats[0].get("url"), **FFMPEG_OPTION)
      source_with_volume = discord.PCMVolumeTransformer(source,volume)

      voice_client.play(source_with_volume, after=after)
  