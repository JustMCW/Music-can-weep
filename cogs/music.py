import discord, youtube_dl, asyncio, time
from datetime import datetime as dt
from urllib.request import urlopen
from discord.ext import commands

from replies import replies
from replit import db
from errors import custom_errors as error_type
from discord_components import Select, SelectOption, Button, ButtonStyle

#----------------------------------------------------------------#
#Emojis (discord)
class Emojis:
  youtube_icon = "<:youtube_icon:937854541666324581>"
  discord_on = "<:discord_on:938107227762475058>"
  discord_off = "<:discord_off:938107694785654894>"
  cute_panda = "<:panda_with_headphone:938476351550259304>"

#Btn message sent and delete after
del_after_sec = 20

#when the volume is 100% the actual volume is gonna be:
initial_volume = 0.5

#Some option when extracting the audio from YT
YDL_OPTION = {
    "format": "bestaudio",
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    # 'restrictfilenames': True,
    'noplaylist': True,
    # 'nocheckcertificate': True,
    # 'ignoreerrors': False,
    # 'logtostderr': False,
    "no_color": True,
    'cachedir': False,
    'quiet': False,
    'no_warnings': False,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}


#----------------------------------------------------------------#


#MESSAGES
class texts:
    #The embed that display the audio's infomation + status
    def audio_playing_embed(self, ctx,requester,info:dict,foundLyrics:bool=False) -> discord.Embed:
        NowplayingEmbed = discord.Embed(title=info["title"],
                                        url=info["webpage_url"],
                                        color=discord.Color.from_rgb(255, 255, 255))

                                        
        NowplayingEmbed.set_author(name=f"Requested by {requester.display_name}",
                                  icon_url=requester.avatar_url)
        # NowplayingEmbed.set_footer(text = f"This song was playing at")

        #Infomation about the video
        NowplayingEmbed.add_field(name=f"YT Channel  {Emojis.youtube_icon}",
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
                                  value=f"{self.get_current_vc(ctx)}",
                                  inline=True)
        NowplayingEmbed.add_field(name="Volume 📶",
                                  value=f"{self.get_volume_percentage(ctx)}",
                                  inline=True)
        NowplayingEmbed.add_field(name="Looping 🔂",
                                  value=f'**{self.get_deco_loop(ctx)}**',
                                  inline=True)

        return NowplayingEmbed

    #some decoration function
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

    @staticmethod
    def number_format(number:int):
        if number.isdigit():
          return f"{number:,}"

#Audio Status
class AudioStates:
  #I store the audio's status

  def is_playing(self, ctx)-> bool:
    if not ctx.voice_client: return False
    return (True if ctx.voice_client.source else False)

  def get_loop(self,ctx)->bool:
    return self.loop.get(ctx.guild.id,True)

  def get_deco_loop(self,ctx)->str:
    return texts.bool_to_str(self.get_loop(ctx))
  
  @staticmethod
  def get_current_vc(ctx):
    return ctx.voice_client.channel.mention

  def get_volume(self,ctx)->float:
    return self.volume.get(ctx.guild.id,initial_volume)

  def get_volume_percentage(self,ctx)->str:
    return f'{round(self.get_volume(ctx) / initial_volume * 100)}%'


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

        from re import sub as ReSub
        return ReSub(r'\[.*?\]', '', copy)
        # while True:
        #     try:
        #         remove = copy[copy.index('<'):copy.index('>') + 1]
        #         copy = copy.replace(remove, '')
        #     except ValueError:
        #         return copy

    @classmethod
    def extract_subtitles(selfClass,subtitles_list:list, language:str)->list:
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
                line = selfClass.filter_subtitle(line)
                if len(subtitles) > 2:
                    if line in subtitles[-1] or line in subtitles[-2]:
                        continue
            subtitles.append(line)
        subtitles_file.close()
        return subtitles

    @staticmethod
    async def send_subtitles(DM, subtitles_text:str):
        full = ""
        for text in subtitles_text:
            if len(full + text) > 1999:
                await DM.send(f"{full}")
                full = ""
            else:
                full += text
        if len(full) > 1: await DM.send(full)


#----------------------------------------------------------------#


#BUTTONS
class buttons:
    def __init__(self, btnmsg, info, currentClass):
        self.btnmsg = btnmsg
        self.info = info
        self.currentClass = currentClass
        self.bot = currentClass.bot

    #blue', 'green', 'grey', 'red', 'URL'

    AudioButtons = [
          [
            Button(label="Pause",
                   custom_id="pause",
                   style=ButtonStyle.blue,
                   emoji="⏸"),
            Button(label="Resume",
                   custom_id="resume",
                   style=ButtonStyle.green,
                   emoji="▶️"),
            Button(label="Stop",
                   custom_id="stop",
                   style=ButtonStyle.red,
                   emoji="⛔"),
            Button(label="Restart",
                   custom_id="restart",
                   style=ButtonStyle.grey,
                   emoji="🔄")
          ],
          [
            Button(label="Favourite",
                  custom_id="fav",
                  style=ButtonStyle.red,
                  emoji="🤍"),
            Button(label="Toggle looping",
                  custom_id="loop",
                  style=ButtonStyle.grey,
                  emoji="🔂"),
            Button(label="Lyrics",
                  custom_id="subtitles",
                  style=ButtonStyle.blue,
                  emoji="✏️")
            
          ]
        ]

    AfterAudioButtons = [
      [
        Button(label="Play this song again ! ",
               custom_id="play_again",
               style=ButtonStyle.blue,
               emoji="🎧"),
        Button(label="Favourite",
               custom_id="fav",
               style=ButtonStyle.red,
               emoji="🤍")
      ]
    ]

    @classmethod
    def get_buttons(selfClass,FoundSubtitles:bool)->list:
        NewAudioButtons = selfClass.AudioButtons.copy()  #Make a clone
        NewAudioButtons[1][2].disabled = not FoundSubtitles #if it's found then dont disable or if is't not found disable it
        return NewAudioButtons

    async def receive_button(self, ctx, button_pressed):
        
        sup = self.currentClass
        author = button_pressed.author
        btnmsg = self.btnmsg
        vc = ctx.voice_client.channel
        vc_members = vc.members
        will_send = len([member
                         for member in vc_members if not member.bot]) > 1
        found, languages = sup.find_subtitle_and_language(self.info)

        if button_pressed.custom_id == "subtitles":
            from langcodes import Language
            await button_pressed.respond(
                type=4, content=f"🗒 {author.mention} Check your DM")
            options = []
            for index, lan in enumerate(languages.keys()):
                languageName = Language.get(lan)
                if not languageName.is_valid(): continue
                options.append(
                    SelectOption(label=languageName.display_name(), value=lan))
                if index == 24: break

            title = self.info["title"]

            UserDM = await author.create_dm()
            ask_msg = await UserDM.send(
                f"🔠 Select subtitles language for ***{title}***",
                components=[
                    Select(placeholder="select language", options=options)
                ])

            try:
                option = await self.bot.wait_for(
                    event='select_option',
                    check=lambda opt: opt.message == ask_msg,
                    timeout=60)
            except:
                await ask_msg.edit(
                    content=
                    "⚙️ This option has expired , try a new one instead!",
                    components=[])
            else:
                selected_language = option.values[0]
                modernLanguageName = Language.get(
                    selected_language).display_name()
                await option.message.delete()
                await UserDM.send(
                    content=f"**{title} [ {modernLanguageName} ] **")
                await sup.send_subtitles(
                    UserDM,
                    f"\n{''.join(sup.extract_subtitles(languages,selected_language))}\n\n( Subtitle from the oringal Youtube video {Emojis.youtube_icon} )"
                )

        if author not in vc_members:
            return await button_pressed.respond(
                type=4,
                content=f"🔊 Join `{vc}` to interact with the audio",
            )

        if button_pressed.custom_id == "loop":
            id = button_pressed.guild_id
            currentloop = self.currentClass.loop.get(id, True)
            self.currentClass.loop[id] = not currentloop
            await button_pressed.edit_origin(
                content=button_pressed.message.content)
            if will_send:
                return await btnmsg.reply(
                    content=
                    f"{sup.loop_audio_msg.format(sup.turn_bool_to_str(not currentloop))} by {author.mention}",
                    delete_after=del_after_sec)

        if button_pressed.custom_id == "restart":
            await sup.restart_audio(ctx)
            await button_pressed.edit_origin(
                content=button_pressed.message.content)
            while not sup.is_playing(ctx):
                await asyncio.sleep(0.5)
            if will_send:
                return await btnmsg.reply(
                    content=f"{sup.restarted_audio_msg} by{author.mention}",
                    delete_after=del_after_sec)

        if button_pressed.custom_id == "pause":
            if ctx.voice_client.is_paused():
                return await button_pressed.respond(
                    type=4, content=sup.already_paused_msg)
            await button_pressed.edit_origin(
                content=button_pressed.message.content)
            sup.pause_audio(ctx)
            if will_send:
                return await btnmsg.reply(
                    content=f"{sup.paused_audio_msg} by{author.mention}",
                    delete_after=del_after_sec)

        if button_pressed.custom_id == "resume":
            if not ctx.voice_client.is_paused():
                return await button_pressed.respond(
                    content=sup.already_resumed_msg)
            await button_pressed.edit_origin(
                content=button_pressed.message.content)
            sup.resume_audio(ctx)
            if will_send:
                return await btnmsg.reply(
                    content=f"{sup.resumed_audio_msg} by {author.mention}",
                    delete_after=del_after_sec)

        if button_pressed.custom_id == "stop":
            await button_pressed.edit_origin(
                content=button_pressed.message.content)
            await sup.stop_audio(ctx)
            if will_send:
                return await btnmsg.reply(
                    content=f"{sup.stopped_audio_msg} by{author.mention}",
                    delete_after=del_after_sec)
        return


#----------------------------------------------------------------#


#FUNCTION
class function:
    async def join_voice_channel(self, ctx, vc):
        #if bot lacks the permission to join / private channel
        for perm in list(ctx.guild.me.permissions_in(vc)):
            if (perm[0] == "connect" or perm[1]) and not perm[1]:
                raise commands.errors.BotMissingPermissions({"connect"})
                
        if ctx.voice_client is None: await vc.connect()
        else: await ctx.voice_client.move_to(vc)

    async def getAudioInfo(self, query)->list:
        with youtube_dl.YoutubeDL(YDL_OPTION) as ydl:
            info = ydl.extract_info(query, download=False)
            if 'entries' in info: info = info["entries"][0]
            return info

    def pause_audio(self, ctx)-> None:
        ctx.voice_client.pause()

    def resume_audio(self, ctx) -> None:
        ctx.voice_client.resume()

    async def stop_audio(self, ctx)-> None:
        id = ctx.guild.id
        orginalValue = self.loop.get(id, True)
        self.loop[id] = "stop"
        ctx.voice_client.stop()
        await asyncio.sleep(.5)
        self.loop[id] = orginalValue

    async def restart_audio(self, ctx)-> None:
        id = ctx.guild.id
        orginalValue = self.loop.get(id, True)
        self.loop[id] = "restart"
        ctx.voice_client.stop()
        await asyncio.sleep(.5)
        self.loop[id] = orginalValue

    #Webscraping in YT
    def searchAudio(self, query, limit=-1)-> list:
        from requests import get
        from bs4 import BeautifulSoup
        from json import loads
        from re import search as ReSearch
        res = get(
            f"https://www.youtube.com/results?search_query={'+'.join(str(w) for w in query.split())}"
        )
        htmlSoup = BeautifulSoup(res.text, "lxml")
        script = [
            s for s in htmlSoup.find_all("script") if "videoRenderer" in str(s)
        ][0]
        extractedScript = ReSearch('var ytInitialData = (.+)[,;]{1}',
                                 str(script)).group(1)
        jsonData = loads(extractedScript)
        queryList = (  #the path
            jsonData["contents"]["twoColumnSearchResultsRenderer"]
            ["primaryContents"]["sectionListRenderer"]["contents"][0]
            ["itemSectionRenderer"]["contents"] )
        formattedQueryList = []

        #Removing non video items (live stream)
        for item in queryList:
            if item.get("videoRenderer"):
                if item["videoRenderer"].get("lengthText"):
                    longText = item["videoRenderer"]["lengthText"][
                        "accessibility"]["accessibilityData"]["label"]
                    if "hours" in longText:
                        if int(ReSearch(r"(.*) hours", longText).group(1)) > 4:
                            continue
                    formattedQueryList.append(item['videoRenderer'])
                    if len(formattedQueryList) == limit: break

        return formattedQueryList

    async def play_audio(self,
                         ctx,
                         audio_url,
                         after=None,
                         position=0) -> None:
        FFMPEG_OPTION = {
            "before_options":
            "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": f"-vn -ss {position}"}
        #Convert format
        source = discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTION)
        source_with_volume = discord.PCMVolumeTransformer(source, self.get_volume(ctx))

        ctx.voice_client.play(source_with_volume, after=after)

    async def repeat_audio(self, ctx, info, start_time):
        voice = ctx.voice_client

        async def SongEnds():
            now_playing = self.now_playing.get(ctx.guild.id)
            if now_playing:
                now_playing_msg = await ctx.fetch_message(now_playing["message_id"])
                newEmbed = now_playing_msg.embeds[0]
                newEmbed.clear_fields()

                await now_playing_msg.edit(embed=newEmbed
                  .add_field(
                      name=f"YT Channel  {Emojis.youtube_icon}",
                      value="[{}]({})".format(info["channel"],info["channel_url"]),
                      inline=True)
                  .add_field(
                      name="Length ↔️",
                      value=f'`{texts.length_format(info.get("duration","Unknown"))}`',
                      inline=True),
                 components=buttons.AfterAudioButtons)

        #Left voice channel
        if not voice:
            return self.bot.loop.create_task(SongEnds())

        #Loop is off
        looping = self.loop.get(ctx.guild.id, True)
        if (looping != True and looping != "restart"):
            self.bot.loop.create_task(SongEnds())
            return voice.stop()

        #counter 403 forbidden error (because unfixable now)
        if (time.time() - start_time) < 2 and looping != "stop":
            print("403 detected !")
            info = await self.getAudioInfo(info["webpage_url"])
        start_time = time.time()

        loop_audio = self.repeat_audio(ctx, info, start_time)

        #Play the audio
        try:
          await self.play_audio(
              ctx=ctx,
              audio_url=info["formats"][0]["url"],
              after=lambda _: asyncio.run(loop_audio),
          )
        except error_type.ClientException:
          self.bot.loop.create_task(SongEnds())

    async def update_audio_msg(self,ctx,msg,foundLyrics:bool,info:dict,requester=None):
        if not self.is_playing(ctx): return
        guildId = ctx.guild.id
        audio_msg = self.now_playing.get(guildId)
        if not audio_msg: return
        try:
          audio_msg = await ctx.fetch_message(audio_msg["message_id"])
        except: 
          return
        orginal_embed = audio_msg.embeds[0]
        
        #Replacing the orignal states field
        for _ in range(3):
          orginal_embed.remove_field(3)

        orginal_embed.insert_field_at(index=3,
                                      name="Voice Channel 🔊",
                                      value=f"*{self.get_current_vc(ctx)}*")
        orginal_embed.insert_field_at(index=4,
                                      name="Volume 📶",
                                      value=f"{self.get_volume_percentage(ctx)}")
        orginal_embed.insert_field_at(index=5,
                                      name="Looping 🔂",
                                      value=f"**{self.get_deco_loop(ctx)}**")
                                            
        await msg.edit(embed=orginal_embed)

    def defaultFav(self, user):
        db["favourites"][str(user.id)] = db["favourites"].get(str(user.id), {})

    def isFavEmpty(self, user)-> bool:
        return len(db['favourites'][str(user.id)]) < 1

    def addToFav(self, user, title:str, url:str):
        usrid = str(user.id)
        if len(db["favourites"][usrid]) + 1 > 25: raise ValueError
        db["favourites"][usrid][title] = url

    def getFavByIndex(self, user, index: int):
        usrid = str(user.id)
        FavList = db['favourites'][usrid]
        if index <= 0 or index > len(FavList):
            raise ValueError
        for position, title in enumerate(FavList):
            if position == (index - 1):
                return title, FavList[title]


#----------------------------------------------------------------#


#COMMANDS
class music_commands(commands.Cog, function, texts, replies, subtitles,AudioStates):
    def __init__(self, bot,log):
        print("MUSIC commands is ready")

        self.bot = bot
        self.log = log

        self.loop = {str:bool}
        self.now_playing = {}
        self.volume = {str:float}
        super().__init__()

#CHANGING BOT'S VOICE CHANNEL

    @commands.command(
        aliases=["enter", "come", "move", "j"],
        description=
        '🎧 Connect to your current voice channel or a given voice channel if specified')
    @commands.bot_has_guild_permissions(connect=True, speak=True)
    async def join(self, ctx, *, ChannelName:str=None):
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
        await super().join_voice_channel(ctx, channel_to_join)

        #Response
        await ctx.reply(super().join_msg.format(channel_to_join.mention))
        await self.log.send(
            f"`{str(dt.now())[:-7]}` - {author} just make me joined `{channel_to_join}` in [{ctx.guild}] ;"
        )

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
        if not super().is_playing(ctx):
            raise error_type.NoAudioPlaying

        super().pause_audio(ctx)

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
        if not super().is_playing(ctx):
            raise error_type.NoAudioPlaying

        super().resume_audio(ctx)

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
        if not super().is_playing(ctx):
            raise error_type.NoAudioPlaying

        await super().stop_audio(ctx)

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
        if not super().is_playing(ctx):
            raise error_type.NoAudioPlaying

        await super().restart_audio(ctx)

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
        vc = ctx.voice_client
        if vc:
          audio = vc.source
          if audio: 
            audio.volume = true_volume

#Set looping

    @commands.guild_only()
    @commands.command(aliases=["looping",'setloop','setlooping','setloopingto','changelooping','set_loop' ,"repeat", 'lop'],
                      description='🔂 Enable / Disable looping')
    async def loop(self, ctx, mode=None):
        id = ctx.guild.id
        if self.loop.get(id, None) is None: self.loop[id] = True
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
                return await ctx.reply(
                    "🪗 Enter a vaild looping mode : `on / off`")
        loop = self.loop[id]
        await ctx.reply(super().loop_audio_msg.format(
            self.bool_to_str(loop)))
        await self.log.send(
            f"`{str(dt.now())[:-7]}` - {ctx.author} set loop to `{loop}` in [{ctx.guild}] ;"
        )
#----------------------------------------------------------------#
#Playing the audio

    @commands.bot_has_guild_permissions(connect=True, speak=True)
    @commands.command(
        aliases=["sing", "music",'playsong',"playmusic","play_song",'play_music', "p"],
        description=
        '🔎 Search and play audio with a given YOUTUBE link or search keyword 🎧'
    )
    async def play(self,
                   ctx,
                   *,
                   Keyword_or_URL,
                   **kwargs):
        if Keyword_or_URL.startswith(
                "https://www.youtube.com/watch?v=") and not kwargs.get("btnRequester"):
            await ctx.trigger_typing()

        author = ctx.author if not kwargs.get("btnRequester") else kwargs["btnRequester"]
        guild_id = ctx.guild.id

        reply_msg = kwargs.get("playAgainMsg") or None

        #See if using is in voice channel
        if not ctx.voice_client and not author.voice:
            raise error_type.UserNotInVoiceChannel

        #Get song from favourites if keyword is captured
        if 'fav' in Keyword_or_URL.lower():
            from re import findall
            try:
                index = int(findall(r'\d+', Keyword_or_URL)[0])
                title, link = super().getFavByIndex(author, index)
                Keyword_or_URL = link
            except:
                return await ctx.reply(
                    "❌ Failed to get song from your favourite list")
            else:
                reply_msg = await ctx.send(
                    f"🎧 Track **#{index}** in {author.mention}'s' favourites has been selected"
                )

        #User select song if not a link
        elif not Keyword_or_URL.startswith("https://www.youtube.com/watch?v="):
            await ctx.trigger_typing()
            query = super().searchAudio(Keyword_or_URL, 5)
            choices = ""
            selectButtons = []
            for i, video in enumerate(query):
                title = video["title"]["runs"][0]["text"]
                length = video["lengthText"]["simpleText"]
                choices += (f'{i+1}: {title} `[{length}]`\n')
                selectButtons.append(
                    Button(label=i + 1,
                           custom_id=str(i),
                           style=ButtonStyle.blue))
            choiceEmbed = discord.Embed(
                title=
                "🎵  Select a song you would like to play : ( click the button below )",
                description=choices,
                color=discord.Color.from_rgb(255, 255, 255))
            selectMsg = await ctx.send(embed=choiceEmbed,
                                       components=[selectButtons])
            TimeOut = 120
            try:
                btn = await self.bot.wait_for(
                    "button_click",
                    timeout=TimeOut,
                    check=lambda btn: btn.author == ctx.author and btn.message
                    == selectMsg)
            except:
                return await selectMsg.edit(embed=discord.Embed(
                    title=f"{Emojis.cute_panda} No track was selected !",
                    description=
                    f"You thought for too long ( {TimeOut//60} minutes ), use the command again !",
                    color=discord.Color.from_rgb(255, 255, 255)),
                                            components=[])
            else:
                #received option
                await selectMsg.delete()
                reply_msg = await ctx.send(
                    content=
                    f"{Emojis.youtube_icon} Song **#{int(btn.custom_id)+1}** in the youtube search result has been selected",
                    mention_author=False)
                Keyword_or_URL = f'https://www.youtube.com/watch?v={query[int(btn.custom_id)]["videoId"]}'


        #Joining Voice channel
        if not ctx.voice_client and author.voice:
            await super().join_voice_channel(
                ctx=ctx,
                vc=author.voice.channel,
            )

        #Stop current audio
        if ctx.voice_client: await super().stop_audio(ctx)

        voice = ctx.voice_client

        await self.log.send(
            f"`{str(dt.now())[:-7]}` - {author} played `{Keyword_or_URL}` at `{voice.channel}` in [{ctx.guild}] ;"
        )

        #Getting the audio file + it's information
        try:
            info = await super().getAudioInfo(Keyword_or_URL)
        #If failed
        except BaseException as unexpection:
            await self.log.send(f"`{str(dt.now())[:-7]}` - an error captured when trying to get info from {Keyword_or_URL} ;")
            await ctx.send(
                f"🤷🏻 I found the video however I cannot play it because :\n`{str(unexpection).replace('ERROR: ','')}`"
            )
        #if success
        else:
            #Play the audio
            loop_audio = super().repeat_audio(ctx,
                                              info=info,
                                              start_time=time.time())
            await super().play_audio(
                ctx=ctx,
                audio_url=info["formats"][0]["url"],
                after=lambda e: asyncio.run(loop_audio),
            )

            #Getting the subtitle
            foundLyrics = super().find_subtitle_and_language(info)[0]

            #the message to send and for controling the audio
            AUDIO_EMBED = self.audio_playing_embed(ctx,author, info,foundLyrics)
            CONTROL_BUTTONS = buttons.get_buttons(foundLyrics)
            if reply_msg:
                await reply_msg.edit(embed=AUDIO_EMBED,
                                     components=CONTROL_BUTTONS)
            else:
                reply_msg = await ctx.send(embed=AUDIO_EMBED,
                                           components=CONTROL_BUTTONS)

            self.now_playing[guild_id] = {
              "message_id":reply_msg.id,
              "channel_id":reply_msg.channel.id,
              "info":info
            }

            #Detect Button Clicking + Update audio message loop
            btns = buttons(reply_msg, info, self)
            while super().is_playing(ctx):
                #Update the Message
    
                await super().update_audio_msg(ctx=ctx,
                                              msg=reply_msg,
                                              foundLyrics = foundLyrics,
                                              info=info,
                                              requester=author)
                try:
                    #Wait for button click
                    button_pressed = await self.bot.wait_for(
                        event='button_click',
                        check=lambda btn: btn.message.id == self.now_playing.
                        get(guild_id)["message_id"]
                        if self.now_playing.get(guild_id) else None,
                        timeout=20)
                except:
                    pass  #when timeout just repeat
                else:
                    await btns.receive_button(ctx, button_pressed)
                finally:  #Check if still the same audio playing
                    now_playing = self.now_playing.get(guild_id)
                    if not now_playing: break  #not playing anything
                    if now_playing["message_id"] != reply_msg.id: break  #changed

            #After the audio has finshed playing -

            #Removing now playing message
            now_playing = self.now_playing.get(ctx.guild.id)
            if now_playing:
                if now_playing["message_id"] == reply_msg.id:
                    del self.now_playing[ctx.guild.id]

#----------------------------------------------------------------#
    @commands.Cog.listener()
    async def on_voice_state_update(self,member, before, after):
      #See if it is a user leaving
      if member.bot or not before.channel: return
      if before.channel.guild.me not in before.channel.members: return
      def get_vc_members_count():
        return len(
            [member for member in before.channel.members 
                if not member.bot])
      
      #no one is in the vc
      if get_vc_members_count() == 0:
        guild= before.channel.guild
        voice_client = guild.voice_client
        now_playing = self.now_playing.get(guild.id)
        if voice_client.source and now_playing:
          channel = await self.bot.fetch_channel(now_playing["channel_id"])
          now_playing_message =await channel.fetch_message(now_playing["message_id"])
          await now_playing_message.reply(
            f"⏸ Paused since nobody is in {before.channel.mention} ( leaves after 30 seconds )",
            delete_after=30)
          voice_client.pause()
        await asyncio.sleep(30)
        if get_vc_members_count() == 0:
          await voice_client.disconnect()

      

#Permanent button detecting

    @commands.Cog.listener()
    async def on_button_click(self, btn):

        await self.log.send(f"`{str(dt.now())[:-7]}` - {btn.author} pressed `{btn.custom_id}` button in [{btn.guild}] ;"
        )
        #Play again button
        if btn.custom_id == "play_again":

            #get ctx object
            ctx = await self.bot.get_context(btn.message)

            #check author voice
            if not ctx.voice_client and not btn.author.voice:
                return await btn.respond(type=4,
                                         content=super().user_not_in_vc_msg)

            URL = btn.message.embeds[0].url
            NowPlaying = self.now_playing.get(ctx.guild.id)
            if NowPlaying:
                if NowPlaying["info"]["webpage_url"] == URL:
                    return await btn.respond(
                        type=4, content="🎵 This song is already playing.")
            
            #Prevents the interaction failed message appearing
            await btn.edit_origin(content=btn.message.content)

            playAgainMsg = await ctx.reply(
                content=f"🎻 {btn.author.mention} requests to play this song again 👍")

            #Play the music
            await ctx.invoke(self.bot.get_command('play'),
                            Keyword_or_URL=URL,
                            playAgainMsg=playAgainMsg,
                            btnRequester=btn.author)

        #Favourite button
        elif btn.custom_id == "fav":
            await btn.respond(type=5)

            self.defaultFav(btn.author)

            title = btn.message.embeds[0].title
            songURL = btn.message.embeds[0].url

            if title not in db["favourites"][str(btn.author.id)]:
                try:
                    super().addToFav(btn.author, title, songURL)
                except:
                    await btn.respond(
                        content=
                        "🎧 You cannot have more than 25 songs in your favourites"
                    )
                else:
                    await btn.respond(
                        content=super().added_fav_msg.format(title))
            else:
                await btn.respond(
                    content=super().already_in_fav_msg.format(title))
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

        #No audio playing (not found the now playing message)
        if not self.now_playing.get(ctx.guild.id):
            return await ctx.reply(super().free_to_use_msg)

        now_playing= self.now_playing.get(ctx.guild.id)
        msgId = now_playing["message_id"]
        info = now_playing["info"]
        #if same text channel
        try:
            msg = await ctx.fetch_message(msgId)
            await msg.reply("*🎧 This is the audio playing right now ~*")
        #Or not
        except:
            await ctx.send(
                f"🎶 Now playing in **{self.get_current_vc(ctx)}** - `{info['title']}`"
            )
#----------------------------------------------------------------#
#Favouriting songs

    @commands.guild_only()
    @commands.command(aliases=['addtofav', "save", "savesong", "fav"],
                      description='❤️ Add the current audio to your favourites')
    async def favourite(self, ctx):

        self.defaultFav(ctx.author)
        #No audio playing
        if not self.now_playing.get(ctx.guild.id):
            return await ctx.reply(super().free_to_use_msg)

        info = self.now_playing.get(ctx.guild.id)["info"]

        await self.log.send(
            f"`{str(dt.now())[:-7]}` - `{ctx.author}` added `[{info['title']}]` to the fav list in [{ctx.guild}] ;"
        )

        #Already in list
        if info["title"] in db['favourites'].get(str(ctx.author.id)):
            return await ctx.reply(super().already_in_fav_msg.format(info['title']))

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
            f"`{str(dt.now())[:-7]}` - `{ctx.author}` used display_favourites command in [{ctx.guild}] ;"
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


#Code ends here