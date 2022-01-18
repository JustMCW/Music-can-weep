import discord,youtube_dl,asyncio,time
from datetime import datetime as dt
from urllib.request import urlopen
from discord.ext import commands
from langcodes import Language

from replies import replies
from replit import db
from errors import custom_errors as error_type
from discord_components import Select, SelectOption, Button, ButtonStyle

#----------------------------------------------------------------#

del_after_sec = 20
update_time = 10

YDL_OPTION = {
  "format":"bestaudio",
  'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
  # 'restrictfilenames': True,
  'noplaylist': True,
  # 'nocheckcertificate': True,
  # 'ignoreerrors': False,
  # 'logtostderr': False,
  "no_color":True,
  'cachedir': False,
  'quiet': True,
  'no_warnings': False,
  'default_search': 'auto',
  'source_address': '0.0.0.0'
}

# 'blue', 'gray', 'green', 'red' ,URL

#----------------------------------------------------------------#

#MESSAGES
class texts:
  def turn_bool_to_str(self,value):
    if value == True: return "On"
    if value == False: return "Off"
    return "UNKNOWN"
  def audio_playing_embed(self,ctx,info,other_info):
    #description = info["description"]
    NPE = discord.Embed(
      title=info["title"],
      url = info["webpage_url"],
      #description = f"{description[:200]}..." if len(description) > 200 else description,
      color=discord.Color.from_rgb(255, 255, 255),
      timestamp=dt.now()
    )
    NPE.set_author(name=f"Requested by {other_info.get('requester').display_name}",icon_url=other_info.get('requester').avatar_url)
    NPE.set_footer(text = f"☑️ This board updates each {update_time} seconds until the audio ends")

    #Infomation about the video
    NPE.add_field(name="YT Channel 📺",value="[{}]({})".format(info["channel"],info["channel_url"]), inline=True)
    NPE.add_field(name="Length ↔️",value=f'`{self.length_format(info.get("duration","Unknown"))}`',inline=True)
    NPE.add_field(name="Upload Date 📆",value=self.date_format(info.get("upload_date","Unknown")),inline=True)
    NPE.add_field(name="Views 👀",value=self.number_format(info.get("view_count","Unknown")),inline=True)
    NPE.add_field(name="Likes 👍",value=self.number_format(info.get("like_count","Unknown")),inline=True)
    NPE.add_field(name="Lyrics 📝",value=f'*{"Available" if other_info.get("lyrics") else "Unavailable"}*',inline=True)
    NPE.set_image(url = info["thumbnail"])

    #About the audio status
    NPE.add_field(name="Voice Channel 🔊",value=f"*{ctx.voice_client.channel}*",inline=True)
    NPE.add_field(name="Volume 📶",value= f"{self.volume.get(str(ctx.guild.id),1)*100}%", inline=True)
    NPE.add_field(name="Looping 🔂",value=f'**{self.turn_bool_to_str(self.loop.get(ctx.guild.id,True))}**',inline=True)
    
    return NPE
  def length_format(self,second:int):
    if second < 3600:
      Min  = str(second//60)
      Sec = str(second%60)
      if len(Sec)== 1:
        Sec = "0"+Sec
      return "{}:{}".format(Min,Sec)
    else:
      Hours = str(second//3600)
      Min = str((second%3600)//60)
      Sec = str(second%3600%60)
      if len(Sec)== 1:
        Sec = "0"+Sec
      if len(Min) == 1:
        Min = "0"+Min
      return "{}:{}:{}".format(Hours,Min,Sec)
  def number_format(self,number):
    try: int(number)
    except: return number

    number = str(number)
    length = len(number)
    result = ""
    for digit,value in enumerate(number):
      if (length - digit)%3 == 0 and digit != 0:
        result += ","
      result += value
    return result
  def date_format(self,dates):
    return f"{dates[:4]}-{dates[4:6]}-{dates[6:]}"

#----------------------------------------------------------------#


#Thing that mess with subtitle
class subtitles:
  def find_subtitle_and_language(self,info):
    sub_catergory = info.get("subtitles",None)
    if sub_catergory is not None:
      if len(sub_catergory) > 0:
        return True,sub_catergory
    return False,None

  def filter_subtitle(self,content):
    copy = content.encode().decode('unicode-escape')
    copy = copy.replace('â','')
    copy = copy.replace('','')
    copy = copy.replace('','')
    while True: 
      try:
        remove = copy[copy.index('<'):copy.index('>')+1]
        copy = copy.replace(remove,'')
      except ValueError: return copy

  def extract_subtitles(self,subtitles_list,language):
    language_catergory = subtitles_list.get(language,None)
    if language_catergory is None : 
      language_catergory = list(subtitles_list.values())[0]
    subtitles_url = language_catergory[4]["url"]
    subtitles_file = urlopen(subtitles_url)
    subtitles = []
    is_complex = False
    for line in subtitles_file:
      if line=="\n".encode('utf-8'): continue
      line = line.decode('utf-8')
      if "##" in line: 
        is_complex = True
        continue
      if line == ' ' or line == '': continue
      stopped_words = ["-->","Kind:","WEBVTT","Language",'::cue','}','Style:']
      if any(x in str(line) for x in stopped_words): continue
      if is_complex: 
        line = self.filter_subtitle(line)
        if len(subtitles)>2:
          if line in subtitles[-1] or line in subtitles[-2]: 
            continue
      subtitles.append(line)
    subtitles_file.close()
    return subtitles

  async def send_subtitles(self,dm,subtitles_text):
    full = ""
    for text in subtitles_text:
      if len(full+text) > 1999:
        await dm.send(f"{full}")
        full = ""
      else:full +=text
    if len(full) > 1: await dm.send(full)


#----------------------------------------------------------------#


#BUTTONS
class buttons:
  def __init__(self,btnmsg,info,currentClass):
    self.btnmsg = btnmsg
    self.info = info
    self.currentClass = currentClass
    self.bot = currentClass.bot
  #blue', 'green', 'grey', 'red', 'URL'
  AudioButtons = [[
    Button(label = "Pause",custom_id = "pause",style=ButtonStyle.blue,emoji = "⏸"),
    Button(label = "Resume",custom_id = "resume",style=ButtonStyle.green,emoji = "▶️"),
    Button(label = "Stop",custom_id = "stop",style=ButtonStyle.red,emoji = "⛔"),
    Button(label = "Restart",custom_id = "restart",style=ButtonStyle.grey,emoji = "🔄")]
  ]
  AfterAudioButtons = [
    [
      Button(
        label = "Play this song again ! ",custom_id = "play_again",
        style=ButtonStyle.blue,emoji = "🎧"
      ),
      Button(      
        label = "Favourite",custom_id = "fav",style=ButtonStyle.red,emoji = "🤍"
      )
    ]
  ]
  def set_buttons(self,looping,FoundSubtitles):
    NewAudioButtons = list(buttons.AudioButtons) #Make a clone
    NewAudioButtons.append([]) #add new row

    NewAudioButtons[1].append(Button(      
      label = "Favourite",
      custom_id = "fav",
      style=ButtonStyle.red,
      emoji = "🤍",)
    )
    NewAudioButtons[1].append(Button(
        label = f"{'Enable' if not looping else 'Disable'} looping",
        custom_id = "loop",
        style=ButtonStyle.green if not looping else ButtonStyle.grey,
        emoji = "🔂",
      )
    )
    NewAudioButtons[1].append(
      Button(      
        label = "Lyrics",
        custom_id = "subtitles",
        style=ButtonStyle.blue,
        emoji = "✏️",
        disabled = not FoundSubtitles
      )
    )
    return NewAudioButtons

  async def receive_button(self,ctx,button_pressed):
    sup = self.currentClass
    author = button_pressed.author
    btnmsg = self.btnmsg
    vc_members = ctx.voice_client.channel.members
    will_send = len([member for member in vc_members if not member.bot]) > 1
    found,languages = sup.find_subtitle_and_language(self.info)
    await self.bot.get_channel(923730161864704030).send(f"`{str(dt.now())[:-7]}` - {author} pressed {button_pressed.custom_id} button in `{ctx.guild}`;")

    if button_pressed.custom_id == "subtitles":
      await button_pressed.respond(type = 4,content =f"🗒 {author.mention} Check your DM")
      options = []
      for index,lan in enumerate(languages.keys()):
        languageName = Language.get(lan)
        if not languageName.is_valid(): continue
        options.append(SelectOption(label=languageName.display_name(),value=lan))
        if index == 24: break
      
      title = self.info["title"]

      UserDM = await author.create_dm()
      ask_msg = await UserDM.send(f"💭 Choose the language you woud like for subtitles of ***{title}***",components = [
        Select(placeholder = "select language",
        options = options)])

      try: 
        option = await self.bot.wait_for(
          event = 'select_option', 
          check= lambda opt:opt.message == ask_msg,
          timeout = 30
        )
      except: 
        await ask_msg.edit(
          content = "⚙️ This option has expired , try a new one !",
          components =[]
        )
      else:
        
        selected_language = option.values[0]
        modernLanguageName = Language.get(selected_language).display_name()
        await option.message.delete()
        await UserDM.send(
          content = f"**{title} [ {modernLanguageName} ]**",
          components =[])
        await sup.send_subtitles(
          UserDM,
          sup.extract_subtitles(languages,selected_language))
        
    elif author not in vc_members: 
      return await button_pressed.respond(
        type = 4,
        content = "👻 You cannot interrupt the audio when you are not in the same voice channel as i do 🔊",
      )

    elif button_pressed.custom_id == "loop":
      id = button_pressed.guild_id
      currentloop = self.currentClass.loop.get(id,True)
      self.currentClass.loop[id] = not currentloop
      newButtons=self.set_buttons(
        looping = not currentloop,
        FoundSubtitles = found)
      await button_pressed.edit_origin(components=newButtons)
      if will_send:
        return await btnmsg.reply(content =
        f"{sup.loop_audio_msg.format(sup.turn_bool_to_str(not currentloop))} by {author.mention}",delete_after = del_after_sec)

    elif button_pressed.custom_id == "restart":
      await sup.restart_audio(ctx)
      await button_pressed.edit_origin(content = sup.now_play_msg)
      while not sup.is_playing(ctx):
        await asyncio.sleep(0.5)
      if will_send:
        return await btnmsg.reply(content = f"{sup.restarted_audio_msg} by{author.mention}",delete_after = del_after_sec)

    if button_pressed.custom_id == "pause":
      if ctx.voice_client.is_paused():
        return await button_pressed.respond(type = 4 ,content = sup.already_paused_msg)
      await button_pressed.edit_origin(content = sup.now_play_msg)
      sup.pause_audio(ctx)
      if will_send:
        return await btnmsg.reply(content = f"{sup.paused_audio_msg} by{author.mention}",delete_after = del_after_sec)

    elif button_pressed.custom_id == "resume":
      if not ctx.voice_client.is_paused():  
        return await button_pressed.respond(content = sup.already_resumed_msg)
      await button_pressed.edit_origin(content = sup.now_play_msg)
      sup.resume_audio(ctx)
      if will_send:
        return await btnmsg.reply(content = f"{sup.resumed_audio_msg} by {author.mention}",delete_after = del_after_sec)

    elif button_pressed.custom_id == "stop":
      await button_pressed.edit_origin(content = sup.now_play_msg)
      await sup.stop_audio(ctx)
      if will_send:
        return await btnmsg.reply(content = f"{sup.stopped_audio_msg} by{author.mention}",delete_after = del_after_sec)
    return


#----------------------------------------------------------------#


#FUNCTION
class function:
  def is_playing(self,ctx):
    if not ctx.voice_client: return False
    if ctx.voice_client.source is not None: return True
    return False

  async def join_voice_channel(self,ctx,vc):
    #if bot lacks the permission to join / private channel
    for perm in list(ctx.guild.me.permissions_in(vc)):
      if (perm[0] == "connect" or perm[1]) and not perm[1]:
        raise commands.errors.BotMissingPermissions({"connect"})
    if ctx.voice_client is None: await vc.connect()
    else: await ctx.voice_client.move_to(vc)

  async def getAudioInfo(self,key):
    with youtube_dl.YoutubeDL(YDL_OPTION) as ydl:
      info = ydl.extract_info(key,download=False)
      if 'entries' in info: info = info["entries"][0]
      return info

  def pause_audio(self,ctx): 
    ctx.voice_client.pause()
    
  def resume_audio(self,ctx): 
    ctx.voice_client.resume()

  async def stop_audio(self,ctx):
    id = ctx.guild.id
    orgin = self.loop.get(id,True)
    self.loop[id] = "stop"
    ctx.voice_client.stop()
    await asyncio.sleep(.5)
    self.loop[id] = orgin

  async def restart_audio(self,ctx):
    id = ctx.guild.id
    orgin = self.loop.get(id,True)
    self.loop[id] = "restart"
    ctx.voice_client.stop()
    await asyncio.sleep(.5)
    self.loop[id] = orgin

  def searchAudio(self,query,limit=-1):
    from requests import get
    from bs4 import BeautifulSoup
    from json import loads
    from re import search
    res = get(f"https://www.youtube.com/results?search_query={'+'.join(str(w) for w in query.split())}")
    htmlSoup = BeautifulSoup(res.text,"lxml")
    script = [s for s in htmlSoup.find_all("script") if "videoRenderer" in str(s)][0]
    extractedScript = search('var ytInitialData = (.+)[,;]{1}', str(script)).group(1)
    jsonData = loads(extractedScript)
    queryList = ( #the path
        jsonData["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"]
        ["sectionListRenderer"]["contents"][0]["itemSectionRenderer"]["contents"] 
    )
    formattedQueryList = []
    #Removing non video items
    for item in queryList:
        if item.get("videoRenderer"):
          if item["videoRenderer"].get("lengthText"):
            formattedQueryList.append(item['videoRenderer'])
            if len(formattedQueryList) == limit: break
    return formattedQueryList


  async def play_audio(self,channel,audio_url,volume,after=None,position = 0):
    FFMPEG_OPTION = {
      "before_options":"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
      "options":f"-vn -ss {position}"
    }
    #Convert format
    source = discord.FFmpegPCMAudio(audio_url,**FFMPEG_OPTION)
    source_with_volume = discord.PCMVolumeTransformer(source,volume)

    channel.play(source_with_volume,after = after)

  async def repeat_audio(self,ctx,info,start_time):
    voice = ctx.voice_client

    async def removeButtons():
      now_playing = self.now_playing.get(ctx.guild.id)
      if now_playing:
        await now_playing[0].edit(
            content = f"**🎧 Audio which was playing:**",
            components= buttons.AfterAudioButtons
          )

    #Left voice channel
    if not voice: 
      return self.bot.loop.create_task(removeButtons())

    #No ones is in the voice channel
    VoiceMembers = [member for member in voice.channel.members if not member.bot]
    
    #Loop is off
    looping = self.loop.get(ctx.guild.id,True)
    if (looping != True and looping != "restart") or len(VoiceMembers) <= 0: 
      self.bot.loop.create_task(removeButtons())
      return voice.stop()
    
    #counter 403 forbidden error (because unfixable now)
    if (time.time()-start_time) < 2 and looping != "stop":
      print("403 detected !")
      info = await self.getAudioInfo(info["webpage_url"])
    start_time=time.time()

    loop_audio = self.repeat_audio(ctx,info,start_time)

    #Play the audio
    await self.play_audio(
      channel = ctx.voice_client,
      audio_url = info["formats"][0]["url"],
      volume = self.volume.get(str(ctx.guild.id),1),
      after = lambda _: asyncio.run(loop_audio),
    )

  async def update_audio_msg(self,ctx,msg,status,requester = None):
    if not msg: return
    found = status.get("found",None)
    otherinfo = {
      "lyrics":found,
      "requester" : requester
    }
    new_embed = self.audio_playing_embed(ctx,status["info"],otherinfo)

    newButtons=buttons.set_buttons(self,self.loop.setdefault(ctx.guild.id,True),found) if self.is_playing(ctx) else None

    if newButtons:
      await msg.edit(embed =new_embed,components = newButtons)

  def defaultFav(self,user):
    db["favourites"][str(user.id)] = db["favourites"].get(str(user.id),{})

  def isFavEmpty(self,user):
    usrid = str(user.id)
    if len(db['favourites'][usrid]) < 1:
      return True
    return False

  def addFav(self,user,title,url):
    usrid = str(user.id)
    if len(db["favourites"][usrid])+1 > 25: raise ValueError
    db["favourites"][usrid][title] = url

  def getFavByIndex(self,user,index:int):
    usrid = str(user.id)
    FavList = db['favourites'][usrid]
    if index <= 0 or index> len(FavList): 
      raise ValueError
    for position,title in enumerate(FavList):
      if position == (index -1):
        return title,FavList[title]
    
#----------------------------------------------------------------#


#COMMANDS
class music_commands(commands.Cog,function,texts,replies,subtitles):

  def __init__(self,bot,log_id):
    self.bot = bot
    self.log = self.bot.get_channel(log_id)
    self.loop = {}
    self.now_playing = {}
    self.volume = {}
    super().__init__()

#CHANGING BOT'S VOICE CHANNEL

  @commands.command(aliases=["enter","come","move","j"],description='🎧 Connect to your current voice channel or a given voice channel if specified')
  @commands.bot_has_guild_permissions(connect = True,speak = True)
  async def join(self,ctx,*,ChannelName = None):
    author = ctx.author
    channel = None
    #if specified a channel
    if ChannelName:
      SelectedVC = discord.utils.get(ctx.guild.voice_channels,name = ChannelName)
      if not SelectedVC: #Channel not found
        raise commands.errors.ChannelNotFound(ChannelName)
      channel = SelectedVC
    #User not in a voice channel
    elif not author.voice: 
      raise error_type.UserNotInVoiceChannel
    else:
      channel = author.voice.channel

    #if already in the that same voice channel
    if ctx.voice_client:
      if channel == ctx.voice_client.channel: 
        return await ctx.reply(super().same_vc_msg.format(channel))

    #Join
    await super().join_voice_channel(ctx,channel)

    #Response
    await ctx.reply(super().join_msg.format(channel))
    await self.log.send(f"`{str(dt.now())[:-7]}` - {author} just make me joined `{channel}` in [{ctx.guild}] ;")
    
  @commands.guild_only()
  @commands.command(aliases=["leave","bye",'dis',"lev","lve",'l'],description='👋 Disconnect from the current voice channel i am in')
  async def disconnect(self,ctx):
    channel = ctx.voice_client

    #Not in a voice channel
    if not channel: raise error_type.NotInVoiceChannel
    
    #Disconnect from channel
    await channel.disconnect()

    #Message
    await ctx.reply(super().leave_msg.format(channel.channel))
    await self.log.send(f"`{str(dt.now())[:-7]}` - {ctx.author} just make me disconnect from `{channel.channel}` in [{ctx.guild}] ;")

#----------------------------------------------------------------#
#INTERRUPTING THE AUDIO

  @commands.guild_only()
  @commands.command(aliases=["wait"],description='⏸ Pause the current audio')
  async def pause(self,ctx):

    #Checking
    if not ctx.voice_client: 
      raise error_type.NotInVoiceChannel
    if not super().is_playing(ctx): 
      raise error_type.NoAudioPlaying

    super().pause_audio(ctx)

    await ctx.reply(super().paused_audio_msg)
    await self.log.send(f"`{str(dt.now())[:-7]}` - {ctx.author} used pause command in [{ctx.guild}] ;")

  @commands.guild_only()
  @commands.command(aliases=["continue","unpause"],description='▶️ Resume the current audio')
  async def resume(self,ctx):

    #Checking
    if not ctx.voice_client: 
      raise error_type.NotInVoiceChannel
    if not super().is_playing(ctx): 
      raise error_type.NoAudioPlaying
    
    super().resume_audio(ctx)
    
    await ctx.reply(super().resumed_audio_msg)
    await self.log.send(f"`{str(dt.now())[:-7]}` - {ctx.author} used resume command in [{ctx.guild}] ;")

  @commands.guild_only()
  @commands.command(aliases=["stop_playing"],description='⏹ stop the current audio from playing 🚫')
  async def stop(self,ctx):
    
    #Checking
    if not ctx.voice_client: 
      raise error_type.NotInVoiceChannel
    if not super().is_playing(ctx):
      raise error_type.NoAudioPlaying

    await super().stop_audio(ctx)

    await ctx.reply(super().stopped_audio_msg)
    await self.log.send(f"`{str(dt.now())[:-7]}` - {ctx.author} used stop command in [{ctx.guild}] ;")
  
  @commands.guild_only()
  @commands.command(aliases=["replay","re"],description='🔄 restart the current audio')
  async def restart(self,ctx):

    #Checking
    if not ctx.voice_client: 
      raise error_type.NotInVoiceChannel
    if not super().is_playing(ctx): 
      raise error_type.NoAudioPlaying

    await super().restart_audio(ctx)
    
    await ctx.reply(super().restarted_audio_msg)
    await self.log.send(f"`{str(dt.now())[:-7]}` - {ctx.author} used restart command in [{ctx.guild}] ;")
#----------------------------------------------------------------#
  @commands.guild_only()
  @commands.command(aliases=["set_volume","vol"],description='📶 set audio volume to a percentage (0% - 150%)')
  async def volume(self,ctx,volume_to_set):

    #Try getting the volume from the message
    try: 
      volume = float(volume_to_set)
      if volume < 0: raise TypeError
    except: 
      return await ctx.reply("🎧 Please enter a vaild volume 🔊")
    
    await self.log.send(f"`{str(dt.now())[:-7]}` - {ctx.author} set volume to `{round(volume,2)}%` in [{ctx.guild}] ;")
   
    #Volume higher than limit
    if volume > 150: 
      return await ctx.reply("🚫 Please enter a volume below 150% (to protect yours and other's ears 👍🏻)")

    await ctx.reply(f"🔊 Volume has been set to {round(volume,2)}%")

    #Setting the volume
    volume = volume / 100
    vc = ctx.voice_client
    audio = vc.source
    self.volume[str(ctx.guild.id)] = volume
    if audio: audio.volume = volume

#Set looping
  @commands.guild_only()
  @commands.command(aliases= ["looping","repeat",'lop'],description='🔂 Enable / Disable looping')
  async def loop(self,ctx,mode= None):
    id = ctx.guild.id
    if self.loop.get(id,None) is None: self.loop[id] = True
    loop = self.loop[id]

    #if not specified a mode
    if not mode: 
      self.loop[id] = not loop
    else:
      on = mode.lower()
      if "on" in on or "tru" in on or 'y' in on:
        self.loop[id] = True
      elif "of" in on or "fal" in on or 'n' in on:
        self.loop[id] = False
      else:
        return await ctx.reply("🪗 Enter a vaild looping mode : `on / off`")

    await ctx.reply(super().loop_audio_msg.format(self.loop[id]))
    await self.log.send(f"`{str(dt.now())[:-7]}` - {ctx.author} set loop to `{loop}` in [{ctx.guild}] ;")
#----------------------------------------------------------------#
#Playing the audio
  @commands.bot_has_guild_permissions(connect = True,speak = True)
  @commands.command(aliases = ["sing","p"],description='🔎 Search and play audio with a given YOUTUBE link or search keyword 🎧')
  async def play(self,ctx,*,Keyword_or_URL,btnRequester = None):
    await ctx.trigger_typing()
    author = ctx.author if not btnRequester else btnRequester
    guild_id = ctx.guild.id

    #Get song from favourites if keyword is captured
    if 'fav' in Keyword_or_URL.lower() and not btnRequester:
      try:
        index = [int(word) for word in Keyword_or_URL.split() if word.isdigit()][0]
        title,link = super().getFavByIndex(author,index)
        Keyword_or_URL = link
      except: 
        return await ctx.reply("❌ Failed to get song from your favourite list")
    
    #See if using is in voice channel
    if not ctx.voice_client and not author.voice:
      raise error_type.UserNotInVoiceChannel

    #User select song if not a link
    if not Keyword_or_URL.startswith("https://www.youtube.com/watch?v=")  and not btnRequester:
      query = super().searchAudio(Keyword_or_URL,5)
      choices = ""
      selectButtons = []
      for i,video in enumerate(query):
          title = video["title"]["runs"][0]["text"]
          length = video["lengthText"]["simpleText"]
          choices+=(f'{i+1}: {title} `[{length}]`\n')
          selectButtons.append(Button(label = i+1,custom_id=str(i),style=ButtonStyle.blue))
      choiceEmbed = discord.Embed(
        title = "🎵 Select a song you would like to play :",
        description =choices,
        color = discord.Color.from_rgb(255,255,255)
      )
      selectMsg = await ctx.send(embed = choiceEmbed,components=[selectButtons])
      try: 
        btn =await self.bot.wait_for("button_click",timeout = 60,check=lambda btn: btn.author == ctx.author and btn.message == selectMsg)
      except:
        return await selectMsg.edit(
          embed = discord.Embed(title = "💭 You did not pick a song to play...", color = discord.Color.from_rgb(255,255,255)),
          components=[])
      else:
        await selectMsg.delete()
        print(btn.custom_id)
        Keyword_or_URL = f'https://www.youtube.com/watch?v={query[int(btn.custom_id)]["videoId"]}'
        await ctx.trigger_typing()
    
    #joining Voice channel
    if not ctx.voice_client and author.voice:
      await super().join_voice_channel(
        ctx = ctx,
        vc = author.voice.channel,
      )
    
    #Stop current audio
    if ctx.voice_client: await super().stop_audio(ctx)

    voice = ctx.voice_client

    await self.log.send(f"`{str(dt.now())[:-7]}` - {author} played `{Keyword_or_URL}` at `{voice.channel}` in [{ctx.guild}] ;")
    
    #Getting the audio + it's information
    try: 
      info = await super().getAudioInfo(Keyword_or_URL)
    #If failed
    except BaseException as unexpection :
      await ctx.reply(f"🤷🏻 I found it however i cannot play it because :\n`{str(unexpection).replace('ERROR: ','')}`")

    #if success
    else: 
      #Play the audio
      loop_audio = super().repeat_audio(ctx,
        info = info,
        start_time = time.time()
      )
      await super().play_audio(
        channel = voice,
        audio_url = info["formats"][0]["url"],
        volume = self.volume.get(guild_id,1),
        after=lambda e: asyncio.run(loop_audio),
      )
      # print(info["formats"][0]["url"])
      #Getting the subtitle
      foundLyrics  = super().find_subtitle_and_language(info)[0]
      
      #the message to send and for controling the audio
      reply_msg = await ctx.send(
        content = super().now_play_msg,
        embed = self.audio_playing_embed(
          ctx,info,{
            "requester":author,
            "lyrics":foundLyrics
          }
        )
      )
      self.now_playing[guild_id] = [reply_msg ,info]

      #Detect Button Clicking + Update audio message loop
      btns = buttons(reply_msg,info,self)
      while super().is_playing(ctx):
        
        try: 
          #Update the Message
          await super().update_audio_msg(ctx,reply_msg,
            {"found":foundLyrics,"info":info,},author)
          #Wait for button click
          button_pressed = await self.bot.wait_for(event = 'button_click', 
          check= lambda btn:btn.message.id == self.now_playing.get(guild_id)[0].id if self.now_playing.get(guild_id) else None,
          timeout = update_time)
        except: pass #when timeout
        else:
          await btns.receive_button(ctx,button_pressed) 
        finally: #Check if still the same audio playing
          now_playing = self.now_playing.get(guild_id)
          if not now_playing: break #not playing anything
          if now_playing[0].id != reply_msg.id: break #changed

      #After the audio has finshed playing -
      await reply_msg.edit(
        content = f"**🎧 Audio which was playing:**",
        components= buttons.AfterAudioButtons
      )
      #Removing now playing message
      now_playing_msg = self.now_playing.get(ctx.guild.id)
      if now_playing_msg: 
        if now_playing_msg[0].id == reply_msg.id:
          del self.now_playing[ctx.guild.id]

    #If not used for a while
    finally:
      await asyncio.sleep(30)
      if ctx.voice_client and not super().is_playing(ctx):
        await ctx.voice_client.disconnect()
#----------------------------------------------------------------#
#Permanent button detecting
  @commands.Cog.listener()
  async def on_button_click(self,btn):
      
    #Play again button
    if btn.custom_id == "play_again":

      await self.log.send(f"`{str(dt.now())[:-7]}` - {btn.author} pressed play again button in [{btn.guild}] ;")

      #get ctx object
      ctx = await self.bot.get_context(btn.message)

      #check author voice
      if not ctx.voice_client and not btn.author.voice:
        return await btn.respond(type = 4,content = super().user_not_in_vc_msg)

      await btn.respond(type = 4 , content =f"🎻 {btn.author.mention} just requested to play this song again 👍🏻",ephemeral=False)

      #Play the music
      await self.play(
        ctx = ctx,
        Keyword_or_URL =btn.message.embeds[0].url,
        btnRequester = btn.author)

    #Favourite button
    elif btn.custom_id == "fav":
      await btn.respond(type=5)
      
      self.defaultFav(btn.author)

      title = btn.message.embeds[0].title
      songURL = btn.message.embeds[0].url

      await self.log.send(f"`{str(dt.now())[:-7]}` - {btn.author} pressed favourite button to favourite `{title}` in [{btn.guild}] ;")

      if title not in db["favourites"][str(btn.author.id)]:
        try: 
          super().addFav(btn.author,title,songURL)
        except: 
          await btn.respond(content = "🎧 You cannot have more than 25 songs in your favourites")
        else: 
          await btn.respond(content = super().added_fav_msg.format(title))
      else:
        await btn.respond(content = super().already_in_fav_msg.format(title))
#----------------------------------------------------------------#
#Now playing
  @commands.guild_only()
  @commands.command(aliases=["np","nowplaying",
  "now"],description='🔊 Display the current audio playing in the server')
  async def now_playing(self,ctx):
    await self.log.send(f"`{str(dt.now())[:-7]}` - {ctx.author} used now playing command in [{ctx.guild}] ;")

    #No audio playing (not found the now playing message)
    if not self.now_playing.get(ctx.guild.id): 
      return await ctx.reply(super().free_to_use_msg)
    
    msg,info = self.now_playing.get(ctx.guild.id)
    
    #if same voice channel
    if msg.channel == ctx.channel:
      await msg.reply("*🎧 This is the audio playing right now ~*")
    #Or not
    else:
      await ctx.reply(f"🎶  ɴᴏᴡ ᴘʟᴀʏɪɴɢ ɪɴ **{ctx.voice_client.channel}** - `{info['title']}`")
#----------------------------------------------------------------#
#Favouriting songs
  @commands.guild_only()
  @commands.command(aliases=['addtofav',"fav"],description='❤️ Add the current audio to your favourites')
  async def favourite(self,ctx):
    
    self.defaultFav(ctx.author)
    #No audio playing
    if not self.now_playing.get(ctx.guild.id): 
      return await ctx.reply(super().free_to_use_msg)

    info = self.now_playing.get(ctx.guild.id)[1]

    await self.log.send(f"`{str(dt.now())[:-7]}` - `{ctx.author}` added `[{info['title']}]` to the fav list in [{ctx.guild}] ;")

    #Already in list
    if info["title"] in db['favourites'].get(str(ctx.author.id)): 
      return await ctx.reply(super().already_in_fav_msg.format(info['title']))

    #Add to the list
    try: 
      super().addFav(ctx.author,info['title'],info['webpage_url'])
    except: 
      return await ctx.reply("🎧 You cannot have more than 25 songs in your favourites")

    #Responding
    await ctx.reply(super().added_fav_msg.format(info["title"]))
    
#Unfavouriting song
  @commands.command(aliases=['unfav','removefromfav'],description='❣🗒 display your all your favourites')
  async def unfavourite(self,ctx,index):
    await self.log.send(f"`{str(dt.now())[:-7]}` - `{ctx.author}` removed `[{index}]` from the fav list in [{ctx.guild}] ;")

    usrid = str(ctx.author.id)
    self.defaultFav(ctx.author)
    #Fav empty
    if super().isFavEmpty(ctx.author): return await ctx.reply(super().fav_empty_msg)
    
    try: 
      pos = int(index)
      title,link = super().getFavByIndex(ctx.author,pos)
    except ValueError: 
      await ctx.reply("✏ Please enter a vaild index")
    else:
      del db['favourites'][usrid][title]
      await ctx.reply(super().removed_fav_msg.format(title))

#Display Favourites
  @commands.command(aliases=['showfav',"favlist"],description='❣🗒 display your all your favourites')
  async def display_favourites(self,ctx):
    await self.log.send(f"`{str(dt.now())[:-7]}` - `{ctx.author}` used display_favourites command in [{ctx.guild}] ;")
    
    self.defaultFav(ctx.author)
    #list empty
    if super().isFavEmpty(ctx.author): 
      return await ctx.reply(super().fav_empty_msg)

    #Grouping the list in string
    favs_list = db["favourites"][str(ctx.author.id)]
    wholeList = ""
    for index,title in enumerate(favs_list):
      wholeList += "***{}.***  [{}]({})\n".format(
        index+1, #the index count
        title, #the title
        favs_list[title] #the url
      )

    #embed =>
    favouritesEmbed = discord.Embed(
      title = f"❣️🎧 {ctx.author.name}'s favourites 🎵",
      description = wholeList,
      color=discord.Color.from_rgb(255, 255, 255),
      timestamp= dt.now())
    favouritesEmbed.set_footer(text = "Your favourites would be the available in every server")

    #sending the embed
    await ctx.reply(embed=favouritesEmbed)

  @commands.command()
  async def playURL(self,ctx,url):
    from requests import get
    from bs4 import BeautifulSoup
    from json import loads
    from re import search
    r = get(url)
    htmlSoup = BeautifulSoup(r.text,"lxml")
    script = [s for s in htmlSoup.find_all("script") if "onResponseReceivedEndpoints" in str(s)]
    extractedScript = search('var ytInitialData = (.+)[,;]{1}', str(script)).group(1)
    jsonData = loads(extractedScript)
    finalURL = jsonData["currentVideoEndpoint"]["watchEndpoint"]["watchEndpointSupportedOnesieConfig"]["html5PlaybackOnesieConfig"]["commonConfig"]["url"]

    await super().play_audio(
      ctx.voice_client,
      finalURL,1,None
    )
#Code ends here

#I know you didn't read the whole code but still thanks for reading //Ou<//