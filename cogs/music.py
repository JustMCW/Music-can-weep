import discord, youtube_dl, asyncio, time
from datetime import datetime as dt
from urllib.request import urlopen
from discord.ext import commands

from replies import Replies
from replit import db
from errors import custom_errors as error_type
from discord_components import Select, SelectOption, Button, ButtonStyle

#----------------------------------------------------------------#
#Emojis (discord)
class Emojis:
  YOUTUBE_ICON = "<:youtube_icon:937854541666324581>"
  discord_on = "<:discord_on:938107227762475058>"
  discord_off = "<:discord_off:938107694785654894>"
  cute_panda = "<:panda_with_headphone:938476351550259304>"

#Btn message sent and delete after
del_after_sec = 20

#when the volume is 100% the actual volume is gonna be:
initial_volume = 0.5

#Some option for extracting the audio from YT
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


#----------------------------------------------------------------#


#MESSAGES
class Texts:
    #The embed that display the audio's infomation + status
    def audio_playing_embed(self, guild,requester,info:dict,foundLyrics:bool) -> discord.Embed:
        NowplayingEmbed = discord.Embed(title=info["title"],
                                        url=info["webpage_url"],
                                        color=discord.Color.from_rgb(255, 255, 255))

                                        
        NowplayingEmbed.set_author(name=f"Requested by {requester.display_name}",
                                  icon_url=requester.avatar_url)
        # NowplayingEmbed.set_footer(text = f"This song was playing at")

        #Infomation about the video
        NowplayingEmbed.add_field(name=f"YT Channel  {Emojis.YOUTUBE_ICON}",
                                  value="[{}]({})".format(info.get("channel"),info.get("channel_url")),
                                  inline=True)
        NowplayingEmbed.add_field(name="Length ↔️",
                                  value=f'`{self.length_format(info.get("duration"))}`',
                                  inline=True)

        # NowplayingEmbed.add_field(name="Upload Date 📆",value=self.date_format(info.get("upload_date","Unknown")),inline=True)
        # NowplayingEmbed.add_field(name="Views 👀",value=self.number_format(info.get("view_count","Unknown")),inline=True)
        # NowplayingEmbed.add_field(name="Likes 👍",value=self.number_format(info.get("like_count","Unknown")),inline=True)
        
        NowplayingEmbed.add_field(name="Lyrics 📝",
                                  value=f'*{"Available" if foundLyrics else "Unavailable"}*',
                                  inline=True)

        #NowplayingEmbed.set_image(url = info["thumbnail"])
        NowplayingEmbed.set_thumbnail(url=info["thumbnail"])

        #Audio status
        NowplayingEmbed.add_field(name="Voice Channel 🔊",
                                  value=f"{self.get_current_vc(guild).mention}",
                                  inline=True)
        NowplayingEmbed.add_field(name="Volume 📶",
                                  value=f"{self.get_volume_percentage(guild)}",
                                  inline=True)
        NowplayingEmbed.add_field(name="Looping 🔂",
                                  value=f'**{self.get_deco_loop(guild)}**',
                                  inline=True)

        return NowplayingEmbed

    #Decoration function
    @staticmethod
    def bool_to_str(value:bool) -> str:
        if value == True: return f"On {Emojis.discord_on}"
        if value == False: return f"Off {Emojis.discord_off}"
        return "Unknown"
        
    @staticmethod
    def length_format(totalSeconds:int) -> str:
        if totalSeconds < 3600:
            Min = totalSeconds // 60
            Sec = totalSeconds % 60
            return f"{Min}:{Sec:02d}"
        else:
            Hours = totalSeconds // 3600
            Min = (totalSeconds % 3600) // 60
            Sec = totalSeconds % 60
            return f"{Hours}:{Min:02d}:{Sec:02d}"

#Audio Status
class VoiceStates:

  @staticmethod
  def is_playing(guild)-> bool:
    if not guild.voice_client: return False
    return (True if guild.voice_client.source else False)

  @staticmethod
  def is_paused(guild)->bool:
    if not VoiceStates.is_playing(guild):return False
    return guild.voice_client.is_paused()

  @staticmethod
  def get_non_bot_vc_members(guild):
    if guild.voice_client:
      return [member for member in guild.voice_client.channel.members if not member.bot]
    return None

  def get_now_playing(self,guild) -> dict:
    return self.now_playing.get(guild.id)

  def get_current_queue(self,guild):
    return self.queue.get(guild.id)._queue

  def get_loop(self,guild)->bool:
    return self.loop.get(guild.id,True)

  def get_deco_loop(self,guild)->str:
    return Texts.bool_to_str(self.get_loop(guild))
  
  @staticmethod
  def get_current_vc(guild):
    return guild.voice_client.channel

  def get_volume(self,guild)->float:
    return self.volume.get(guild.id,initial_volume)

  def get_volume_percentage(self,guild)->str:
    return f'{round(self.get_volume(guild) / initial_volume * 100)}%'

  
#----------------------------------------------------------------#


#Thing that mess with subtitle
class subtitles:
    @staticmethod
    def find_subtitle_and_language(info:dict)->(bool,list):
        sub_catergory = info.get("subtitles")
        if sub_catergory:
            if len(sub_catergory) > 0:
                return True, sub_catergory
        return False, None

    @staticmethod
    def filter_subtitle(content:str)->str:
        copy = content.encode().decode('unicode-escape')
        copy = copy.replace('â', '').replace('', '').replace('', '')

        # from re import sub as ReSub
        # return ReSub(r'\[.*?\]', '', copy)
        while True:
            try:
                remove = copy[copy.index('<'):copy.index('>') + 1]
                copy = copy.replace(remove, '')
            except ValueError:
                return copy

    @classmethod
    def extract_subtitles(self,subtitles_list:list, language:str)->list:
        language_catergory = subtitles_list.get(language)
        if not language_catergory:
            language_catergory = list(subtitles_list.values())[0]
        subtitles_url = language_catergory[4]["url"]
        subtitles_file = urlopen(subtitles_url)
        subtitles = []
        is_complex = False
        for line in subtitles_file:
            if line == "\n".encode('utf-8'): continue
            line = line.decode('utf-8')
            if "##" in line:
                is_complex = True
                continue
            if line == ' ' or line == '': continue
            skipKeywords = [
                "-->", "Kind:", "WEBVTT", "Language", '::cue', '}', 'Style:'
            ]
            if any(x in str(line) for x in skipKeywords): continue
            if is_complex:
                line = self.filter_subtitle(line)
                if len(subtitles) > 2:
                    if line in subtitles[-1] or line in subtitles[-2]:
                        continue
            subtitles.append(line)
        subtitles_file.close()
        return subtitles

    @staticmethod
    async def send_subtitles(channel, subtitles_text:str):
        full = ""
        for text in subtitles_text.splitlines():
            if len(full + text) > 1999:
                await channel.send(f"{full}")
                full = ""
            else:
                full += text+"\n"
        if len(full) > 1: await channel.send(full)


#----------------------------------------------------------------#


#BUTTONS
class Buttons:
  #Button Templates
    PauseButton = Button(label="Pause",
                          custom_id="pause",
                          style=ButtonStyle.blue,
                          emoji="⏸")
    ResumeButton = Button(label="Resume",
                          custom_id="resume",
                          style=ButtonStyle.green,
                          emoji="▶️")
    StopButton = Button(label="Stop",
                        custom_id="stop",
                        style=ButtonStyle.red,
                        emoji="⛔")
    RestartButton = Button(label="Restart",
                            custom_id="restart",
                            style=ButtonStyle.grey,
                            emoji="🔄")

    FavouriteButton = Button(label="Favourite",
                              custom_id="fav",
                              style=ButtonStyle.red,
                              emoji="🤍")
    LoopButton = Button(label="Toggle looping",
                        custom_id="loop",
                        style=ButtonStyle.grey,
                        emoji="🔂")
    SubtitlesButton = Button(label="Lyrics",
                            custom_id="subtitles",
                            style=ButtonStyle.blue,
                            emoji="✏️")  
    PlayAgainButton = Button(label="Play this song again !",
                              custom_id="play_again",
                              style=ButtonStyle.blue,
                              emoji="🎧")

    AudioControllerButtons=[
        [PauseButton,ResumeButton,StopButton,RestartButton],
        [FavouriteButton,LoopButton,SubtitlesButton]
      ].copy()

    AfterAudioButtons=[[PlayAgainButton,FavouriteButton]].copy()

  #Buttons functionality 
    @staticmethod
    def more_than_one_member(guild) -> bool:
      vc_members = guild.voice_client.channel.members
      return len([member for member in vc_members if not member.bot]) > 1
    
    @classmethod
    async def inform_changes(self,btn,msg):
      if self.more_than_one_member(btn.guild):
        await btn.message.reply(content=f"{msg} by {btn.author.mention}",
                                delete_after=del_after_sec)

    async def on_pause_btn_press(self,btn):
      if self.is_paused(btn.guild):
        await btn.respond(type=4, content=Replies.already_paused_msg)
      else:
        await btn.edit_origin(content=btn.message.content)
        self.pause_audio(btn.guild)
        await self.inform_changes(btn,Replies.paused_audio_msg)

    async def on_resume_btn_press(self,btn):
      if not self.is_paused(btn.guild):
        await btn.respond(type=4, content=Replies.already_resumed_msg)
      else:
        await btn.edit_origin(content=btn.message.content)
        self.resume_audio(btn.guild)
        await self.inform_changes(btn,Replies.resumed_audio_msg)

    async def on_stop_btn_press(self,btn):
      await btn.edit_origin(content=btn.message.content)
      await self.stop_audio(btn.guild)
      await self.inform_changes(btn,Replies.stopped_audio_msg)

    async def on_restart_btn_press(self,btn):
      await btn.edit_origin(content=btn.message.content)
      await self.restart_audio(btn.guild)
      await self.inform_changes(btn,Replies.restarted_audio_msg)

    async def on_loop_btn_press(self,btn):
      await btn.edit_origin(content=btn.message.content)
      currentloop = self.get_loop(btn.guild)
      self.loop[btn.guild_id] = not currentloop
      await self.inform_changes(btn,
        Replies.loop_audio_msg.format(self.get_deco_loop(btn.guild)
        )
      )

    async def on_favourite_btn_press(self,btn):
      await btn.respond(type=5)
      self.defaultFav(btn.author)
      title = btn.message.embeds[0].title
      songURL = btn.message.embeds[0].url
      if title not in db["favourites"][str(btn.author.id)]:
        try:
           self.addToFav(btn.author, title, songURL)
        except:
          await btn.respond(content="🎧 You cannot have more than 25 songs in your favourites")
        else:
          await btn.respond(content=Replies.added_fav_msg.format(title))
      else:
        await btn.respond(content=Replies.already_in_fav_msg.format(title))

    async def on_subtitles_btn_press(self,btn):
      await btn.respond(type=5)
      info = self.get_now_playing(btn.guild)["info"]
      found,languages =self.find_subtitle_and_language(info)
      if not found: return

      from langcodes import Language

      options = []
      for index, lan in enumerate(languages.keys()):
        languageName = Language.get(lan)
        if not languageName.is_valid(): continue
        options.append(
          SelectOption(label=languageName.display_name(), value=lan))
        if index == 24: break

      title = info["title"]

      
      await btn.respond(
        type=4,
        content = f"🔠 Select subtitles language for ***{title}***",
        components=[
          Select(placeholder="select language", options=options)
        ]
      )
      try:
        option = await self.bot.wait_for(
          event='select_option',
          check=lambda opt: opt.author == btn.author,
          timeout=60)
      except:
        pass
      else:
        selected_language = option.values[0]
        modernLanguageName = Language.get(
        selected_language).display_name()

        UserDM = await option.author.create_dm()
        await UserDM.send(
          content=f"**{title} [ {modernLanguageName} ] **")
        await self.send_subtitles(
          UserDM,
          f"{''.join(self.extract_subtitles(languages,selected_language))}"
        )


    async def on_play_again_btn_press(self,btn):
      ctx = await self.bot.get_context(btn.message)
      guild = btn.guild

      URL = btn.message.embeds[0].url
      now_playing = self.get_now_playing(guild)
      
      if now_playing:
        if now_playing["info"]["webpage_url"] == URL:
          return await btn.respond(type=4, 
                                  content="🎵 This song is already playing.")

      #Play the music
      await ctx.invoke(self.bot.get_command('play'),
                        query=URL,
                        btn=btn)


#----------------------------------------------------------------#


#FUNCTION
class function:

    @staticmethod
    async def join_voice_channel(guild, vc):
        try:
          if guild.voice_client is None: await vc.connect()
          else: await guild.voice_client.move_to(vc)
        except: 
          raise commands.errors.BotMissingPermissions({"connect"})

    @staticmethod
    def pause_audio(guild):
      if not guild.voice_client: 
        raise error_type.NotInVoiceChannel
      guild.voice_client.pause()

    @staticmethod
    def resume_audio(guild):
      if not guild.voice_client: 
        raise error_type.NotInVoiceChannel
      guild.voice_client.resume()

    async def stop_audio(self,guild):
      if not guild.voice_client: 
        raise error_type.NotInVoiceChannel

      id = guild.id
      orginalValue = self.loop.get(id, True)
      self.loop[id] = "stop"
      guild.voice_client.stop()
      await asyncio.sleep(.5)
      self.loop[id] = orginalValue

    async def restart_audio(self,guild):
      if not guild.voice_client: 
        raise error_type.NotInVoiceChannel

      id = guild.id
      orginalValue = self.loop.get(id, True)
      self.loop[id] = "restart"
      guild.voice_client.stop()
      await asyncio.sleep(.5)
      self.loop[id] = orginalValue

    #Search Audio fromm Youtube
    @staticmethod
    def searchAudio(query:str, limit=25)-> list:
        from requests import get
        from bs4 import BeautifulSoup
        from json import loads
        from re import search as ReSearch
        httpResponse = get(
          f"https://www.youtube.com/results?search_query={'+'.join(word for word in query.split())}"
        )
        htmlSoup = BeautifulSoup(httpResponse.text, "lxml")

        #Get the scripts ( get rid of other elements such as the search bar and side bar )
        script = [
          s for s in htmlSoup.find_all("script") 
            if "videoRenderer" in str(s)
        ][0]

        #Filter the script into datas
        extractedScript = ReSearch('var ytInitialData = (.+)[,;]{1}',
                                 str(script)).group(1)
        jsonData = loads(extractedScript)

        #The Path to the search results
        queryList = (  
            jsonData["contents"]["twoColumnSearchResultsRenderer"]
            ["primaryContents"]["sectionListRenderer"]["contents"][0]
            ["itemSectionRenderer"]["contents"] )

        
        #Filters items in the search result
        FilteredQueryList = []
        for item in queryList:
            if item.get("videoRenderer"): #Remove channels / playlist
                if item["videoRenderer"].get("lengthText"): #Remove live stream (they have no length)
                    longText = item["videoRenderer"]["lengthText"][
                        "accessibility"]["accessibilityData"]["label"]
                    if "hours" in longText:
                        #Remove video with 3+ hours duration video
                        if int(ReSearch(r"(.*) hours", longText).group(1)) > 3: 
                          continue
                    FilteredQueryList.append(item['videoRenderer'])
                    if len(FilteredQueryList) == limit: break

        return FilteredQueryList

    @staticmethod
    async def getAudioInfo(query)->list:
        with youtube_dl.YoutubeDL(YDL_OPTION) as ydl:
          info = ydl.extract_info(query, download=False)
          if 'entries' in info: info = info["entries"][0]
          return info

    async def play_audio(self,
                         guild,
                         audio_url,
                         after=None,
                         position=0) -> None:
        FFMPEG_OPTION = {
            "before_options":
            "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": f"-vn -ss {position}"}
        #Converting the format
        source = discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTION)
        source_with_volume = discord.PCMVolumeTransformer(source,self.get_volume(guild))

        guild.voice_client.play(source_with_volume, after=after)

    async def after_playing(self, guild, start_time,webpage_url,formats,**_):
        voice = guild.voice_client
        looping = self.get_loop(guild)
        #Left voice channel
        if not voice:
            self.bot.loop.create_task(self.clear_audio_message(guild,webpage_url))
            return print("Left VC")
        #counter 403 forbidden error (because unfixable now)
        elif (time.time() - start_time)<1 and looping not in ["stop","restart"]:
            print("403 detected !")
            #Get a new piece of info
            formats = await self.getAudioInfo(webpage_url)
            formats = formats["formats"]
        #Looping is off
        elif not looping or looping == "stop":
          self.bot.loop.create_task(self.clear_audio_message(guild,webpage_url))
          voice.stop()
          return print(f"Loop off or stopped")

        #Repeat the song
        else:
          new_start_time =float(time.time())

          #Play the audio
          await self.play_audio(
                guild=guild,
                audio_url=formats[0]["url"],
                after=lambda _: asyncio.run(
                  self.after_playing(guild,new_start_time,webpage_url,formats)
                )
          )

    async def update_audio_msg(self,guild):
        if not self.is_playing(guild): return
        audio_msg = self.get_now_playing(guild)
        if not audio_msg: 
          return
        try:
          channel = guild.get_channel(audio_msg.get("channel_id"))
          audio_msg = await channel.fetch_message(audio_msg["message_id"])
        except: 
          return
        new_embed = audio_msg.embeds[0]
        
        #Replacing the orignal states field
        for _ in range(3):
          new_embed.remove_field(3)

        new_embed.insert_field_at(index=3,
                                  name="Voice Channel 🔊",
                                  value=f"*{self.get_current_vc(guild).mention}*")
        new_embed.insert_field_at(index=4,
                                  name="Volume 📶",
                                  value=f"{self.get_volume_percentage(guild)}")
        new_embed.insert_field_at(index=5,
                                  name="Looping 🔂",
                                  value=f"**{self.get_deco_loop(guild)}**")

        #Apply the changes                  
        await audio_msg.edit(embed=new_embed)
        
    async def clear_audio_message(self,guild,webpage_url):
      now_playing = self.get_now_playing(guild)
      if now_playing:
        try:
          channel = self.bot.get_channel(now_playing["channel_id"])
          now_playing_msg =await channel.fetch_message(now_playing["message_id"])
        except discord.errors.NotFound: 
          return print("Message not found or deleted.") #Someone deleted the orignal message
        finally:
          if self.get_now_playing(guild)["info"]["webpage_url"] == webpage_url:
            #Removing now playing message
            del self.now_playing[guild.id]

        newEmbed = now_playing_msg.embeds[0]
        for _ in range(4):
          newEmbed.remove_field(2)

        await now_playing_msg.edit(
          embed=newEmbed,
          components=Buttons.AfterAudioButtons)

        
        
        
class Favourties:
    @staticmethod
    def defaultFav(user):
        db["favourites"][str(user.id)] = db["favourites"].get(str(user.id), {})

    @staticmethod
    def isFavEmpty(user)-> bool:
        return len(db['favourites'][str(user.id)]) < 1

    @staticmethod
    def addToFav(user, title:str, url:str):
        usrid = str(user.id)
        if len(db["favourites"][usrid]) + 1 > 25: 
          raise ValueError
        db["favourites"][usrid][title] = url
    
    @staticmethod
    def getFavByIndex(user, index: int):
        usrid = str(user.id)
        FavList = db['favourites'][usrid]
        if index <= 0 or index > len(FavList):
            raise ValueError
        for position, title in enumerate(FavList):
            if position == (index - 1):
                return title, FavList[title]


#----------------------------------------------------------------#


#COMMANDS
class music_commands(commands.Cog, 
  function, 
  Texts,
  Favourties,
  Replies,
  subtitles,
  VoiceStates,
  Buttons
):
    def __init__(self,bot,log):
        print("MUSIC commands is ready")

        self.bot = bot
        self.log = log

        self.loop = {int:bool}
        self.now_playing = {int:{"message_id":int,
                                  "channel_id":int,
                                  "info":dict}}

        self.volume = {int:float}
        super().__init__()

#CHANGING BOT'S VOICE CHANNEL
    @commands.bot_has_guild_permissions(connect=True, speak=True)
    @commands.command(
        aliases=["enter", "come", "move", "j"],
        description=
        '🎧 Connect to your current voice channel or a given voice channel if specified')
    async def join(self, ctx,*,ChannelName=None):
        author = ctx.author
        channel_to_join = None
        #if specified a channel
        if ChannelName:
            SelectedVC = discord.utils.get(ctx.guild.voice_channels,
                                          name=ChannelName)
            if not SelectedVC:  #Channel not found
              raise commands.errors.ChannelNotFound(ChannelName)
            channel_to_join = SelectedVC
          
        #User not in a voice channel
        elif not author.voice:
            raise error_type.UserNotInVoiceChannel
        else:
            channel_to_join = author.voice.channel

        #if already in the that same voice channel
        if ctx.voice_client:
            if channel_to_join == ctx.voice_client.channel:
                return await ctx.reply(super().same_vc_msg.format(channel_to_join.mention))

        #Join
        await super().join_voice_channel(ctx.guild, channel_to_join)

        #Response
        await ctx.reply(super().join_msg.format(channel_to_join.mention))
        await self.log.send(
            f"`{str(dt.now())[:-7]}` - {author} just make me joined `{channel_to_join}` in [{ctx.guild}] ;"
        )
        await super().update_audio_msg(ctx.guild)

    @commands.guild_only()
    @commands.command(
        aliases=["leave", "bye", 'dis', "lev", "lve", 'l'],
        description='👋 Disconnect from the current voice channel i am in')
    async def disconnect(self, ctx):
        voice_client = ctx.voice_client

        #Not in a voice voice_client
        if not voice_client: raise error_type.NotInVoiceChannel

        #Disconnect from voice_client
        await voice_client.disconnect()

        #Message
        await ctx.reply(super().leave_msg.format(voice_client.channel.mention))
        await self.log.send(
            f"`{str(dt.now())[:-7]}` - {ctx.author} just make me disconnect from `{voice_client.channel}` in [{ctx.guild}] ;"
        )

#----------------------------------------------------------------#
#INTERRUPTING THE AUDIO

    @commands.guild_only()
    @commands.command(aliases=["wait"],
                      description='⏸ Pause the current audio')
    async def pause(self, ctx):

        #Checking
        if not ctx.voice_client:
            raise error_type.NotInVoiceChannel
        if not super().is_playing(ctx.guild):
            raise error_type.NoAudioPlaying

        super().pause_audio(ctx.guild)

        await ctx.reply(super().paused_audio_msg)
        await self.log.send(
            f"`{str(dt.now())[:-7]}` - {ctx.author} used pause command in [{ctx.guild}] ;"
        )

    @commands.guild_only()
    @commands.command(aliases=["continue", "unpause"],
                      description='▶️ Resume the current audio')
    async def resume(self, ctx):

        #Checking
        if not ctx.voice_client:
            raise error_type.NotInVoiceChannel
        if not super().is_playing(ctx.guild):
            raise error_type.NoAudioPlaying

        super().resume_audio(ctx.guild)

        await ctx.reply(super().resumed_audio_msg)
        await self.log.send(
            f"`{str(dt.now())[:-7]}` - {ctx.author} used resume command in [{ctx.guild}] ;"
        )

    @commands.guild_only()
    @commands.command(aliases=["stop_playing"],
                      description='⏹ stop the current audio from playing 🚫')
    async def stop(self, ctx):

        #Checking
        if not ctx.voice_client:
            raise error_type.NotInVoiceChannel
        if not super().is_playing(ctx.guild):
            raise error_type.NoAudioPlaying

        await super().stop_audio(ctx.guild)

        await ctx.reply(super().stopped_audio_msg)
        await self.log.send(
            f"`{str(dt.now())[:-7]}` - {ctx.author} used stop command in [{ctx.guild}] ;"
        )

    @commands.guild_only()
    @commands.command(aliases=["replay", "re"],
                      description='🔄 restart the current audio')
    async def restart(self, ctx):

        #Checking
        if not ctx.voice_client:
            raise error_type.NotInVoiceChannel
        if not super().is_playing(ctx.guild):
            raise error_type.NoAudioPlaying

        await super().restart_audio(ctx.guild)

        await ctx.reply(super().restarted_audio_msg)
        await self.log.send(
            f"`{str(dt.now())[:-7]}` - {ctx.author} used restart command in [{ctx.guild}] ;"
        )
#----------------------------------------------------------------#

    @commands.guild_only()
    @commands.command(
        aliases=["set_volume",'setvolume','setvolumeto','set_volume_to',"changevolume", "vol"],
        description='📶 set audio volume to a percentage (0% - 150%)')
    async def volume(self, ctx, volume_to_set):

        #Try getting the volume_percentage from the message
        try:
            volume_percentage = float(volume_to_set)
            if volume_percentage < 0: raise TypeError
        except:
            return await ctx.reply("🎧 Please enter a vaild volume_percentage 🔊")

        await self.log.send(
            f"`{str(dt.now())[:-7]}` - {ctx.author} set volume to `{round(volume_percentage,2)}%` in [{ctx.guild}] ;")

        PERCENTAGE_LIMIT = 200
        #Volume higher than limit
        if volume_percentage > PERCENTAGE_LIMIT:
            return await ctx.reply(
                f"🚫 Please enter a volume below {PERCENTAGE_LIMIT}% (to protect yours and other's ears 👍🏻)"
            )

        await ctx.reply(f"🔊 Volume has been set to {round(volume_percentage,2)}%")

        #Setting the actual volume we are going to set
        true_volume = volume_percentage / 100 * initial_volume
        
        self.volume[ctx.guild.id] = true_volume
        await super().update_audio_msg(ctx.guild)
        vc = ctx.voice_client
        if vc:
          audio = vc.source
          if audio: 
            audio.volume = true_volume

#Set looping

    @commands.guild_only()
    @commands.command(aliases=["looping",'setloop','setlooping','setloopingto',"toggleloop","toggle_looping",'changelooping','set_loop' ,"repeat", 'lop'],
                      description='🔂 Enable / Disable looping')
    async def loop(self, ctx, mode=None):
        guild = ctx.guild
      
        new_loop = self.get_loop(guild)
        self.loop[guild.id] = new_loop
      
        #if not specified a mode
        if not mode:
          new_loop = not new_loop
        else:
          on = mode.lower()
          if "on" in on or "tru" in on or 'y' in on:
            new_loop = True
          elif "of" in on or "fal" in on or 'n' in on:
            new_loop = False
          else:
            return await ctx.reply("🪗 Enter a vaild looping mode : `on / off`")
    
        self.loop[guild.id] = new_loop
        await ctx.reply(super().loop_audio_msg.format(Texts.bool_to_str(new_loop)))
        await super().update_audio_msg(ctx.guild)

        await self.log.send( f"`{str(dt.now())[:-7]}` - {ctx.author} set loop to `{new_loop}` in [{ctx.guild}] ;")
        
#----------------------------------------------------------------#
#Playing the audio

    @commands.bot_has_guild_permissions(connect=True, speak=True)
    @commands.command(
        aliases=["sing",'playsong',"playmusic","play_song",'play_music', "p"],
        description=
        '🔎 Search and play audio with a given YOUTUBE link or from keywords 🎧'
    )
    async def play(self,ctx,*,query,**kwargs):

        btn = kwargs.get("btn")
        
        if query.startswith("https://www.youtube.com/watch?v=") and not btn:
          await ctx.trigger_typing()

        author = ctx.author if not btn else btn.author
        guild = ctx.guild #even its button it is still gonna be the same guild

        await self.log.send(f"`{str(dt.now())[:-7]}` - {author} trys to play `{query}` in [{guild}] ;")

        #See if using is in voice channel
        if not guild.voice_client and not author.voice:
          if not btn:
            raise error_type.UserNotInVoiceChannel
          else:
            return await btn.respond(type=4,
                                    content=Replies.user_not_in_vc_msg)
        elif btn:
          await btn.edit_origin(content=btn.message.content)
          
        reply_msg = await ctx.reply(
          content=f"🎻 {btn.author.mention} requests to play this song again 👍"
        ) if btn else None
      
        
        if not btn:
          #Get song from favourites if user want song from their fav
          if 'fav' in query.lower():
              from re import findall
              try:
                  index = int(findall(r'\d+', query)[0])
                  title, link = super().getFavByIndex(author, index)
                  query = link
              except:
                  return await ctx.reply(
                      "❌ Failed to get song from your favourite list")
              else:
                  reply_msg = await ctx.send(
                      f"🎧 Track **#{index}** in {author.mention}'s' favourites has been selected"
                  )
                
          #If URL
          elif query.startswith("https://"):
              if query.startswith("https://www.youtube.com/watch?v="): 
                reply_msg = await ctx.send(f"{Emojis.YOUTUBE_ICON} A Youtube link is selected ✅")
              #Not youtube video link
              else:
                return await ctx.send("💿 Sorry ! But only Youtube video links can be played !")
                
          #Let user select song if it's keyword 
          else:
              await ctx.trigger_typing()
              #Searching
              searchResult = super().searchAudio(query,limit=5)
  
              #Add the buttons and texts for user to see
              choicesString = ""
              selectButtons = []
              for i, video in enumerate(searchResult):
                  title = video["title"]["runs"][0]["text"]
                  length = video["lengthText"]["simpleText"]
                  choicesString += (f'{i+1}: {title} `[{length}]`\n')
                  selectButtons.append(Button(label=str(i+1),
                                              custom_id=str(i),
                                              style=ButtonStyle.blue))
  
              #Send those buttons and texts
              selectMsg = await ctx.send(embed=discord.Embed(
                  title="🎵  Select a song you would like to play : ( click the button below )",
                  description=choicesString,
                  color=discord.Color.from_rgb(255, 255, 255))
                  ,components=[selectButtons])
              
              #Get which button user pressed
              TimeOutSeconds = 60 * 2
              try:
                  btn = await self.bot.wait_for(
                      "button_click",
                      timeout=TimeOutSeconds,
                      check=lambda btn: btn.author == author and btn.message.id == selectMsg.id)
              except:
                  #Timeout !
                  return await selectMsg.edit(embed=
                      discord.Embed(
                        title=f"{Emojis.cute_panda} No track was selected !",
                        description=f"You thought for too long ( {TimeOutSeconds//60} minutes ), use the command again !",
                        color=discord.Color.from_rgb(255, 255, 255)
                      )
                    ,components=[])
              else:
                  #Received option
                  btn.responded = True
                  await selectMsg.delete()
                  reply_msg = await ctx.send(
                      content=
                      f"{Emojis.YOUTUBE_ICON} Song **#{int(btn.custom_id)+1}** in the youtube search result has been selected",
                      mention_author=False)
                  query = f'https://www.youtube.com/watch?v={searchResult[int(btn.custom_id)]["videoId"]}'

        #------

        #Getting the audio file + it's information
        try:
            info = await super().getAudioInfo(query)
        #If failed
        except BaseException as unexpection:
            await self.log.send(f"`{str(dt.now())[:-7]}` - an error captured when trying to get info from {query} : {unexpection} ;")
            await ctx.send(
                f"🤷🏻 I found the video however I cannot play it because :\n`{str(unexpection).replace('ERROR: ','')}`"
            )
        #if success
        else:
          #Stop current audio if in voice channel
          if guild.voice_client: 
            await super().stop_audio(guild)
            
          #Join Voice channel
          elif author.voice:
              await super().join_voice_channel(guild=guild,
                                              vc=author.voice.channel)

          #Repeat function after the audio
          start_time = time.time()
          repeat = lambda error: asyncio.run(
            self.after_playing(guild,start_time,**info))

          #Play the audio
          await super().play_audio(guild=guild,
                                  audio_url=info["formats"][0]["url"],
                                  after=repeat)
          
          #Getting the subtitle
          FoundLyrics = super().find_subtitle_and_language(info)[0]

          #the message for displaying and controling the audio

          AUDIO_EMBED = self.audio_playing_embed(guild,author,info,FoundLyrics)
          CONTROL_BUTTONS = Buttons.AudioControllerButtons
          
          #if it's found then dont disable or if is't not found disable it
          CONTROL_BUTTONS[1][2].disabled = not FoundLyrics 

          self.now_playing[guild.id] = {"message_id":reply_msg.id,
                                        "channel_id":reply_msg.channel.id,
                                        "info":info}
          
          await reply_msg.edit(embed=AUDIO_EMBED,
                              components=CONTROL_BUTTONS)

#----------------------------------------------------------------#
    @commands.Cog.listener()
    async def on_voice_state_update(self,member, before, after):
      channel = before.channel or after.channel
      guild = channel.guild
      voice_client = guild.voice_client

      if not voice_client: 
        return 

      #If it is a user leaving a vc
      if not member.bot and before.channel: 
        #The bot is in that voice channel that the user left
        if guild.me in before.channel.members:
          #And no one is in the vc anymore
          if not self.get_non_bot_vc_members(guild):
            
            now_playing = self.now_playing.get(guild.id)

            #Pause if it's playing stuff
            if voice_client.source and now_playing:
              channel = self.bot.get_channel(now_playing["channel_id"])
              await channel.send(
                f"⏸ Paused since nobody is in {before.channel.mention} ( leaves after 30 seconds )",
                delete_after=30)
              voice_client.pause()
            
            #Leave the vc if after 30 second still no one is in vc
            await asyncio.sleep(30)
            if voice_client and not self.get_non_bot_vc_members(guild):
              await voice_client.disconnect()
      #---------------------#
      #Bot moved channel
      elif member == self.bot.user and before.channel and after.channel: #Moving channel
        if voice_client:
          super().pause_audio(before.channel.guild)

#Button detecting

    @commands.Cog.listener()
    async def on_button_click(self, btn):
        
        await self.log.send(f"`{str(dt.now())[:-7]}` - {btn.author} pressed `{btn.custom_id}` button in [{btn.guild}] ;")
        
        if btn.responded or not btn.guild: return
        
        now_playing = super().get_now_playing(btn.guild)
        #Buttons ( Read their name )
        if btn.custom_id == Buttons.FavouriteButton.custom_id:
          await super().on_favourite_btn_press(btn)

        elif btn.custom_id == Buttons.PlayAgainButton.custom_id:
          await super().on_play_again_btn_press(btn)

        elif not now_playing or now_playing.get("message_id") != btn.message.id :
          if not btn.custom_id.isnumeric() and not btn.responded and btn.message.embeds:
            
            new_embed = btn.message.embeds[0]
            
            for _ in range(4):
              new_embed.remove_field(2)

            await btn.edit_origin(embed = new_embed,
                                  components=Buttons.AfterAudioButtons)

        elif btn.custom_id == Buttons.SubtitlesButton.custom_id:
          await super().on_subtitles_btn_press(btn)
        elif btn.custom_id == Buttons.PauseButton.custom_id:
          await super().on_pause_btn_press(btn)
        elif btn.custom_id == Buttons.ResumeButton.custom_id:
          await super().on_resume_btn_press(btn)
        elif btn.custom_id == Buttons.LoopButton.custom_id:
          await super().on_loop_btn_press(btn)
          await super().update_audio_msg(btn.guild)

        elif btn.custom_id == Buttons.RestartButton.custom_id:
          await super().on_restart_btn_press(btn)
        elif btn.custom_id == Buttons.StopButton.custom_id:
          await super().on_stop_btn_press(btn)

#----------------------------------------------------------------#
#Now playing

    @commands.guild_only()
    @commands.command(
        aliases=["np", "nowplaying", "now"],
        description='🔊 Display the current audio playing in the server')
    async def now_playing(self, ctx):
        await self.log.send(
            f"`{str(dt.now())[:-7]}` - {ctx.author} used now playing command in [{ctx.guild}] ;"
        )

        now_playing= super().get_now_playing(ctx.guild)

        #No audio playing (not found the now playing message)
        if not now_playing:
            return await ctx.reply(Replies.free_to_use_msg)
        
        #if same text channel
        try:
            msg = await ctx.fetch_message(now_playing["message_id"])
            await msg.reply("*🎧 This is the audio playing right now ~*")
        #Or not
        except:
            await ctx.send(
                f"🎶 Now playing in {self.get_current_vc(ctx.guild).mention} - **{now_playing['info'].get('title')}**"
            )
#----------------------------------------------------------------#
#Favourites

    @commands.guild_only()
    @commands.command(aliases=['addtofav', "save", "savesong", "fav"],
                      description='👍🏻 Add the current song playing to your favourites')
    async def favourite(self, ctx):

        self.defaultFav(ctx.author)
        #No audio playing
        now_playing = self.get_now_playing(ctx.guild)
        if not now_playing:
            return await ctx.reply(Replies.free_to_use_msg)

        info = now_playing.get("info")

        await self.log.send(
            f"`{str(dt.now())[:-7]}` - `{ctx.author}` added `[{info['title']}]` to the fav list in [{ctx.guild}] ;"
        )

        #Already in list
        if info["title"] in db['favourites'].get(str(ctx.author.id)):
            return await ctx.reply(Replies.already_in_fav_msg.format(info['title']))

        #Add to the list
        try:
            super().addToFav(ctx.author, info['title'], info['webpage_url'])
        except:
            return await ctx.reply(
                "🎧 You cannot have more than 25 songs in your favourites")

        #Responding
        await ctx.reply(super().added_fav_msg.format(info["title"]))

#Unfavouriting song

    @commands.command(aliases=['unfav', 'removefromfav'],
                      description='❣🗒 Remove a song from your favourites')
    async def unfavourite(self, ctx, index):
        await self.log.send(
            f"`{str(dt.now())[:-7]}` - `{ctx.author}` removed `[{index}]` from the fav list in [{ctx.guild}] ;")

        usrid = str(ctx.author.id)
        self.defaultFav(ctx.author)
        #Fav empty
        if super().isFavEmpty(ctx.author):
            return await ctx.reply(super().fav_empty_msg)

        try:
            from re import findall
            index = int(findall(r'\d+', index)[0])
            title,link = super().getFavByIndex(ctx.author, index)
        except ValueError:
            await ctx.reply("✏ Please enter a vaild index")
        else:
            del db['favourites'][usrid][title]
            await ctx.reply(super().removed_fav_msg.format(title))

#Display Favourites

    @commands.command(aliases=[
        'showfav', "favlist", "myfavourites", "myfavourite", "myfavs", "myfav"
    ],
                      description='❣🗒 Display every song in your favourites')
    async def display_favourites(self, ctx):
        await self.log.send(
            f"`{str(dt.now())[:-7]}` - {ctx.author} used display_favourites command in [{ctx.guild}] ;"
        )

        self.defaultFav(ctx.author)
        #list empty
        if super().isFavEmpty(ctx.author):
            return await ctx.reply(super().fav_empty_msg)

        #Grouping the list in string
        favs_list = db["favourites"][str(ctx.author.id)]
        wholeList = ""
        for index, title in enumerate(favs_list):
            wholeList += "***{}.*** {}\n".format(
                index + 1,  #the index count
                title,  #the title
                #favs_list[title] #the url
            )

        #embed =>
        favouritesEmbed = discord.Embed(
            title=f"🤍 🎧 Favourites of {ctx.author.name} 🎵",
            description=wholeList,
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=dt.now())
        favouritesEmbed.set_footer(
            text="Your favourites would be the available in every server")

        #sending the embed
        await ctx.reply(embed=favouritesEmbed)



def setup(BOT):
  from main import BOT_INFO
  Log,ErrorLog = BOT_INFO.getLogsChannel(BOT)
  BOT.add_cog(music_commands(BOT,Log))

#Code ends here 