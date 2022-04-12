import discord, asyncio,time
from datetime import datetime
from discord.ext import commands
from discord_components import Select, SelectOption, Button, ButtonStyle
from main import BOT_INFO
from log import Logging

from convert import Convert
from favourites import Favourties
from subtitles import Subtitles

from Music.queue import SongQueue
from Music.song_track import SongTrack
from Music.voice_state import VoiceState

from replies import Replies
from errors import custom_errors as error_type
from discord_emojis import Emojis

#----------------------------------------------------------------#

#Btn message sent and delete after
del_after_sec = 60
TimeOutSeconds = 60 * 2

#----------------------------------------------------------------#

#MESSAGES
class Embeds:


    #The embed that display the audio's infomation + status
    def audio_playing_embed(queue:SongQueue,foundLyrics:bool) -> discord.Embed:
        SongTrackPlaying:SongTrack = queue[0]

        return discord.Embed(title= SongTrackPlaying.title,
                            url= SongTrackPlaying.webpage_url,
                            color=discord.Color.from_rgb(255, 255, 255))\
                \
                .set_author(name=f"Requested by {SongTrackPlaying.requester.display_name}",
                            icon_url=SongTrackPlaying.requester.avatar_url)\
                .set_thumbnail(url = SongTrackPlaying.thumbnail)\
                \
                .add_field(name=f"YT Channel  {Emojis.YOUTUBE_ICON}",
                            value="[{}]({})".format(getattr(SongTrackPlaying,"channel"),getattr(SongTrackPlaying,"channel_url")))\
                .add_field(name="Length ↔️",
                            value=f'`{Convert.length_format(getattr(SongTrackPlaying,"duration"))}`')\
                .add_field(name="Lyrics 📝",
                            value=f'*{"Available" if foundLyrics else "Unavailable"}*')\
                \
                .add_field(name="Voice Channel 🔊",
                            value=f"{queue.guild.voice_client.channel.mention}")\
                .add_field(name="Volume 📶",
                            value=f"`{round(queue.volume / BOT_INFO.InitialVolume * 100)}%`")\
                .add_field(name="Looping 🔂",
                            value=f'**{Convert.bool_to_str(queue.looping)}**')

    NoTrackSelectedEmbed = discord.Embed(title=f"{Emojis.cute_panda} No track was selected !",
                                        description=f"You thought for too long ( {TimeOutSeconds//60} minutes ), use the command again !",
                                        color=discord.Color.from_rgb(255, 255, 255))
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
    SkipButton = Button(label="Skip",
                        custom_id="Skip",
                        style=ButtonStyle.blue,
                        emoji="⏩")
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

    AudioControllerButtons=[[PauseButton,ResumeButton,SkipButton,RestartButton],
                            [FavouriteButton,LoopButton,SubtitlesButton]].copy()

    AfterAudioButtons=[[PlayAgainButton,FavouriteButton]].copy()

    #Buttons functionality 
    
    async def inform_changes(self,btn,msg:str):
        if len(self.get_non_bot_vc_members(btn.guild)) > 1:
            await btn.message.reply(content=f"{msg} by {btn.author.mention}",
                                    delete_after=del_after_sec)

    async def on_pause_btn_press(self,btn):
      if self.is_paused(btn.guild):
        await btn.respond(type=4, content=Replies.already_paused_msg)
      else:
        await btn.edit_origin(content=btn.message.content)
        await self.pause_audio(btn.guild)
        await self.inform_changes(btn,Replies.paused_audio_msg)

    async def on_resume_btn_press(self,btn):
      if not self.is_paused(btn.guild):
        await btn.respond(type=4, content=Replies.already_resumed_msg)
      else:
        await btn.edit_origin(content=btn.message.content)
        await self.resume_audio(btn.guild)
        await self.inform_changes(btn,Replies.resumed_audio_msg)

    async def on_skip_btn_press(self,btn):
      await btn.edit_origin(content=btn.message.content)
      await self.skip_audio(btn.guild)
      await self.inform_changes(btn,Replies.stopped_audio_msg)

    async def on_restart_btn_press(self,btn):
      await btn.edit_origin(content=btn.message.content)
      await self.restart_audio(btn.guild)
      await self.inform_changes(btn,Replies.restarted_audio_msg)

    async def on_loop_btn_press(self,btn):
      await btn.edit_origin(content=btn.message.content)
      current_loop = self.get_loop(btn.guild)
      self.get_queue(btn.guild).looping = not current_loop
      await self.inform_changes(btn,Replies.loop_audio_msg.format(Convert.bool_to_str(self.get_loop(btn.guild))))

    async def on_favourite_btn_press(self,btn):
      await btn.respond(type=5)
      title = btn.message.embeds[0].title
      url = btn.message.embeds[0].url
      Favourties.add_track(btn.author, title, url)
      await btn.respond(content=Replies.added_fav_msg.format(title))

    async def on_subtitles_btn_press(self,btn):
        await btn.respond(type=5)
        CurrentTrack = self.get_queue(btn.guild)[0]

        languages =getattr(CurrentTrack,"subtitles",None)
        if languages is None: 
            return

        from langcodes import Language

        options = []
        for lan in languages.keys():
                languageName = Language.get(lan)
                if languageName.is_valid(): 
                    options.append(SelectOption(label=languageName.display_name(), value=lan))
                    if len(options) == 24: 
                        break

        title = CurrentTrack.title

        
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
        except asyncio.TimeoutError:
            pass
        else:
            selected_language = option.values[0]
            modernLanguageName = Language.get(
            selected_language).display_name()

            UserDM = await option.author.create_dm()
            await UserDM.send(
            content=f"**{title} [ {modernLanguageName} ] **")
            url,subtitle_text = Subtitles.extract_subtitles(languages,selected_language)
            await Subtitles.send_subtitles(
            UserDM,
            f"{''.join(subtitle_text)}"
            )
            await UserDM.send(content=f"( The subtitle looks glitched ? View the source text file here : {url})")

    async def on_play_again_btn_press(self,btn):
      ctx = await self.bot.get_context(btn.message)
      guild = btn.guild

      URL = btn.message.embeds[0].url

      #Play the music
      await ctx.invoke(self.bot.get_command('play'),
                        query=URL,
                        btn=btn)

#----------------------------------------------------------------#

#FUNCTION
class Functions:

    #Search Audio fromm Youtube
    @staticmethod
    def search_from_youtube(query:str, 
                            ResultLengthLimit:int=5,
                             DurationLimit:int=3*3600) -> list:
        from requests import get
        from bs4 import BeautifulSoup
        from json import loads
        from re import search as ReSearch

        #Send the request and grab the html text
        httpResponse = get(f"https://www.youtube.com/results?search_query={'+'.join(word for word in query.split())}")
        htmlSoup = BeautifulSoup(httpResponse.text, "lxml")

        #Fliter the html soup ( get rid of other elements such as the search bar and side bar )
        scripts = [s for s in htmlSoup.find_all("script") if "videoRenderer" in str(s)][0]

        #Find the data we need among the scripts, and load it into json
        JsonScript = ReSearch('var ytInitialData = (.+)[,;]{1}',str(scripts)).group(1)
        JsonData = loads(JsonScript)

        #The Path to the search results
        QueryList = JsonData["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"]\
                            ["sectionListRenderer"]["contents"][0]["itemSectionRenderer"]["contents"] 

        #Filters items in the search result
        FilteredQueryList = []
        for item in QueryList:
            VidRend = item.get("videoRenderer")
            if VidRend and VidRend.get("lengthText"): #Remove channels / playlist / live stream (live has no time length)
                longText = VidRend["lengthText"]["accessibility"]["accessibilityData"]["label"]
                if "hours" in longText:
                    #Remove video with 3+ hours duration
                    if int(ReSearch(r"(.*) hours", longText).group(1)) > DurationLimit: 
                        continue
                FilteredQueryList.append(VidRend)
                
                #Result length
                if len(FilteredQueryList) == ResultLengthLimit: 
                    return FilteredQueryList

    async def create_audio_message(self,Track:SongTrack,Target):

        #Getting the subtitle
        FoundLyrics = Subtitles.find_subtitle_and_language(getattr(Track,"subtitles",None))[0]

        guild = Target.guild
        queue = self.get_queue(guild)
        #the message for displaying and controling the audio

        AUDIO_EMBED = Embeds.audio_playing_embed(queue,FoundLyrics)
        CONTROL_BUTTONS = Buttons.AudioControllerButtons
        
        #if it's found then dont disable or if is't not found disable it
        CONTROL_BUTTONS[1][2].disabled = not FoundLyrics 

        if isinstance(Target,discord.Message):
            await Target.edit(embed=AUDIO_EMBED,
                                components=CONTROL_BUTTONS)
            Target = await Target.channel.fetch_message(Target.id)

        elif isinstance(Target,discord.TextChannel):
            Target = await Target.send(embed=AUDIO_EMBED,
                                            components=CONTROL_BUTTONS)
        
        queue.audio_message = Target

    def after_playing(self,
                    guild:discord.Guild, 
                    start_time:float,
                    voice_error:str = None):
        
        if voice_error is not None:
            return print("Voice error :",voice_error)

        voice_client:discord.VoiceClient = guild.voice_client
        queue:SongQueue = self.get_queue(guild)
        audio_control_status:str = queue.audio_control_status

        FinshedTrack:SongTrack = queue[0]

        queue.audio_control_status = None

        #Some checks before continue
        #Ensure in voice chat
        if not voice_client:
            self.bot.loop.create_task(self.clear_audio_message(guild))

            if not queue.enabled:
                queue.popleft()

            return print("Ignore loop : NOT IN VOICE CHANNEL")
        
        #Ignore if some commands are triggered
        if audio_control_status == "RESTART":

            return print(f"Ignore loop : RESTART")

        elif audio_control_status == "CLEAR":
            self.bot.loop.create_task(self.clear_audio_message(guild))
            return print("Ignore loop : CLEAR QUEUE")
           
        NextTrack:SongTrack = None
        looping:bool = queue.looping
        
        #Counter 403 forbidden error (an error that try cannot catch, it makes the audio ends instantly)
        if (time.perf_counter() - start_time) < 0.5 and audio_control_status is None:

            print("Ignore loop : HTTP ERROR, Time (ns) = ",time.perf_counter() - start_time)

            #Get a new piece of info
            NextTrack = SongTrack.create_track(query = FinshedTrack.webpage_url,
                                               requester=FinshedTrack.requester)

            #Replace the old info
            queue[0].formats = NextTrack.formats
        
        elif not queue.enabled and (not looping or audio_control_status=="SKIP"):
            queue.popleft()
            self.bot.loop.create_task(self.clear_audio_message(guild))
            return print("Queue disabled")

        #Single song looping is on
        elif looping and audio_control_status is None:
            NextTrack = FinshedTrack

        #Finshed naturaly / skipped
        else:
            queue_looping:bool = queue.queue_looping

            #if queue loop is on
            if audio_control_status == "REWIND":
                queue.rotate(1)
            elif queue_looping:
                queue.rotate(-1)    
            else:
                queue.popleft()

            #Get the next song ( first song in the queue )
            NextTrack = queue.get(0)

            #No song in the queue
            if NextTrack is None:
                
                self.bot.loop.create_task(self.clear_audio_message(guild))
                self.bot.loop.create_task(queue.audio_message.channel.send("\\☑️ All tracks in the queue has been played (if you want to repeat the queue, run \" >>queue repeat on \")",delete_after=30))
                return print("Queue is empty")

            #To prevent sending the same audio message again
            if NextTrack != FinshedTrack:
                print("Next track !")

                async def display_next():

                    target = queue.audio_message.channel

                    if queue.audio_message.content:

                        history = target.history(limit = 2)
                        history = await history.flatten()
                        
                        for msg in history:
                            if msg.id == queue.audio_message.id:
                                target = await target.fetch_message(msg.id)

                        if isinstance(target,discord.TextChannel):
                            await self.clear_audio_message(guild)
                            
                    await self.create_audio_message(Track = NextTrack,
                                                    Target = target)
                  
                
                self.bot.loop.create_task(display_next())
            
            elif audio_control_status == "SKIP":
                
                self.bot.loop.create_task(self.clear_audio_message(guild))
                return print("Skipped the only song in the queue")

        #To show that we have handle the control
        

        new_start_time =float(time.perf_counter())

        #Play the audio
        NextTrack.play(voice_client,
                      after=lambda error: self.after_playing(guild,new_start_time,error),
                      volume=self.get_volume(guild))

    async def update_audio_msg(self,guild):
        if not self.is_playing(guild): 
            return

        audio_msg:discord.Message = self.get_queue(guild).audio_message

        if audio_msg is None: 
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
                                  value=f"**{Convert.bool_to_str(self.get_loop(guild))}**")

        #Apply the changes                  
        await audio_msg.edit(embed=new_embed)
        
    async def clear_audio_message(self,guild):
        queue = self.get_queue(guild)
        audio_message:discord.Message = queue.audio_message

        if audio_message is None:  
            return print("Audio message is none")

        newEmbed:discord.Embed = audio_message.embeds[0]
        for _ in range(4):
            newEmbed.remove_field(2)

        content = audio_message.content #if len(audio_message.content) >1 else "☕️ Audio playing before :"

        await audio_message.edit(content = content,
                                    embed=newEmbed,
                                    components=Buttons.AfterAudioButtons)
        print("Succesfully removed audio messsage.")
        queue.audio_message = None

#----------------------------------------------------------------#

#COMMANDS
class music_commands\
(
  commands.Cog, 
  Functions, 
  VoiceState,
  Buttons
):
    def __init__(self,bot):
        print("MUSIC commands is ready")

        self.bot = bot

        #Hash maps
        self.queues = {int:SongQueue}

        super().__init__()

#CHANGING BOT'S VOICE CHANNEL
    @commands.bot_has_guild_permissions(connect=True, speak=True)
    @commands.command(aliases=["enter", "come", "move", "j"],
                    description='🎧 Connect to your current voice channel or a given voice channel if specified')
    async def join(self, ctx:commands.Context,*,ChannelName=None):
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
                return await ctx.reply(Replies.same_vc_msg.format(channel_to_join.mention))

        #Join
        await super().join_voice_channel(ctx.guild, channel_to_join)

        #Response
        await ctx.reply(Replies.join_msg.format(channel_to_join.mention))
        await Logging.log(f"{author} just make me joined `{channel_to_join}` in [{ctx.guild}] ;")
        await super().update_audio_msg(ctx.guild)

    @commands.guild_only()
    @commands.command(
        aliases=["leave", "bye", 'dis', "lev","leav", "lve", 'l'],
        description='👋 Disconnect from the current voice channel i am in')
    async def disconnect(self, ctx:commands.Context):
        voice_client = ctx.voice_client

        #Not in a voice voice_client
        if not voice_client: 
            raise error_type.NotInVoiceChannel

        #Disconnect from voice_client
        await voice_client.disconnect()

        #Message
        await ctx.reply(Replies.leave_msg.format(voice_client.channel.mention))
        await Logging.log(f"{ctx.author} just make me disconnect from `{voice_client.channel}` in [{ctx.guild}] ;")

#----------------------------------------------------------------#
#INTERRUPTING THE AUDIO

    @commands.guild_only()
    @commands.command(aliases=["wait"],
                      description='⏸ Pause the current audio')
    async def pause(self, ctx:commands.Context):

        await self.pause_audio(ctx.guild)

        await ctx.reply(Replies.paused_audio_msg)
        await Logging.log(
            f"{ctx.author} used pause command in [{ctx.guild}] ;"
        )

    @commands.guild_only()
    @commands.command(aliases=["continue", "unpause"],
                      description='▶️ Resume the current audio')
    async def resume(self, ctx:commands.Context):
        guild = ctx.guild
        queue = self.get_queue(guild)      

        #Not playing anything but the queue has something
        if queue.get(0) is not None:
            try:
                await self.resume_audio(guild)       
            except (error_type.NotInVoiceChannel,error_type.NoAudioPlaying):

                if guild.voice_client is None:
                    try:
                        await self.join_voice_channel(guild, ctx.author.voice.channel)
                    except AttributeError:
                        raise error_type.NotInVoiceChannel

                #Repeat function after the audio
                start_time = float(time.perf_counter())
                after_playing = lambda voice_error: self.after_playing(guild,start_time,voice_error)

                #Play the audio
                queue[0].play(guild.voice_client,
                              volume = self.get_volume(guild),
                              after = after_playing)

                continue_playing_queue_msg = await ctx.send("▶️ Continue to play tracks in the queue")
                await self.create_audio_message(queue[0],continue_playing_queue_msg)
            else:
                await ctx.reply(Replies.resumed_audio_msg)
        else:
            await self.resume_audio(guild)
            await ctx.reply(Replies.resumed_audio_msg)
        
        await Logging.log(f"{ctx.author} used resume command in [{ctx.guild}] ;")


    @commands.guild_only()
    @commands.command(aliases=["previous"],
                      description="⏪ Return to the last song played")
    async def last(self, ctx:commands.Context):

        await self.rewind_audio(ctx.guild)

        await ctx.reply(Replies.rewind_audio_msg)
        await Logging.log(f"{ctx.author} used rewind command in [{ctx.guild}] ;")



    @commands.guild_only()
    @commands.command(aliases=["next"],
                      description='⏩ skip to the next audio in the queue')
    async def skip(self, ctx:commands.Context):
        
        await self.skip_audio(ctx.guild)

        await ctx.reply(Replies.skipped_audio_msg)
        await Logging.log(f"{ctx.author} used skip command in [{ctx.guild}] ;")

    @commands.guild_only()
    @commands.command(aliases=["jump","jumpto"],
                      description="⏏️ Move the time position of the current audio, format : [Hours:Minutes:Seconds] or literal seconds like 3600 (an hour). This is a experimental command.")
    async def seek(self,ctx:commands.Context,*,time_position):

        try:
            position_sec:float = Convert.time_to_sec(time_position)
            await self.restart_audio(ctx.guild,position=position_sec)
        except ValueError:
            await ctx.reply(f"Invaild time position, format : {ctx.prefix}{ctx.invoked_with} [Hours:Minutes:Seconds]")
        except OverflowError:
            await ctx.reply("This time position is longer than the duration of the current track playing")
        else:
            await ctx.reply(f"⏏️ Successfully moved audio's time position to `{Convert.length_format(position_sec)}`")


    @commands.guild_only()
    @commands.command(aliases=["stop_playing"],
                      description='⏹ stop the current audio from playing 🚫')
    async def stop(self, ctx:commands.Context):

        #Checking
        if not ctx.voice_client:
            raise error_type.NotInVoiceChannel
        if not ctx.voice_client.is_playing():
            raise error_type.NoAudioPlaying
        
        await ctx.voice_client.disconnect()

        await ctx.reply(Replies.stopped_audio_msg)

        await Logging.log(
            f"{ctx.author} used stop command in [{ctx.guild}] ;"
        )

    @commands.guild_only()
    @commands.command(aliases=["replay", "re"],
                      description='🔄 restart the current audio')
    async def restart(self, ctx:commands.Context):

        await self.restart_audio(ctx.guild)

        await ctx.reply(Replies.restarted_audio_msg)
        await Logging.log(f"{ctx.author} used restart command in [{ctx.guild}] ;")
#----------------------------------------------------------------#

    @commands.guild_only()
    @commands.command(
        aliases=["set_volume",'setvolume','setvolumeto','set_volume_to',"changevolume", "vol"],
        description='📶 set audio volume to a percentage (0% - 150%)')
    async def volume(self, ctx:commands.Context, volume_to_set):

        #Try getting the volume_percentage from the message
        try:
            volume_percentage = float(volume_to_set)
            if volume_percentage < 0: 
                raise ValueError
        except ValueError:
            return await ctx.reply("🎧 Please enter a vaild volume_percentage 🔊")

        await Logging.log(
            f"{ctx.author} set volume to `{round(volume_percentage,2)}%` in [{ctx.guild}] ;")

        PERCENTAGE_LIMIT = 200
        #Volume higher than limit
        if volume_percentage > PERCENTAGE_LIMIT:
            return await ctx.reply(
                f"🚫 Please enter a volume below {PERCENTAGE_LIMIT}% (to protect yours and other's ears 👍🏻)"
            )

        #Setting the actual volume we are going to set
        true_volume = volume_percentage / 100 * BOT_INFO.InitialVolume
        
        self.get_queue(ctx.guild).volume = true_volume

        await self.update_audio_msg(ctx.guild)
        vc = ctx.voice_client
        if vc and vc.source:
            vc.source.volume = true_volume
            
        await ctx.reply(f"🔊 Volume has been set to {round(volume_percentage,2)}%")

    @commands.guild_only()
    @commands.command(aliases=["looping","single_loop",'setloop','setlooping','setloopingto',"toggleloop","toggle_looping",'changelooping','set_loop' ,"repeat", 'lop'],
                      description='🔂 Enable / Disable looping, when enabled song will restart after playing')
    async def loop(self, ctx:commands.Context, mode=None):
        guild = ctx.guild
      
        new_loop = self.get_loop(guild)

        #if not specified a mode
        if not mode:
          new_loop = not new_loop
        else:
          new_loop = Convert.str_to_bool(mode)
          if new_loop is None:
            return await ctx.reply(Replies.invaild_mode_msg)

        self.get_queue(guild).looping = new_loop
        await ctx.reply(Replies.loop_audio_msg.format(
            Convert.bool_to_str(self.get_loop(guild))
        ))
        await super().update_audio_msg(guild)

        await Logging.log(f"{ctx.author} set loop to `{new_loop}` in [{guild}] ;")
        
#----------------------------------------------------------------#
#Playing audio

    @commands.bot_has_guild_permissions(connect=True, speak=True)
    @commands.command(
        aliases=["sing",'playsong',"playmusic","play_song",'play_music', "p"],
        description=
        '🔎 Search and play audio with a given YOUTUBE link or from keywords 🎧'
    )
    async def play(self,ctx,*,query,**kwargs):

        await ctx.trigger_typing()

        btn = kwargs.get("btn")
        
        author = ctx.author if not btn else btn.author
        guild = ctx.guild

        await Logging.log(f"{author} trys to play `{query}` in [{guild}] ;")

        #See if user is in voice channel
        if not guild.voice_client and not author.voice:
            if not btn:
                raise error_type.UserNotInVoiceChannel
            else:
                return await btn.respond(type=4,
                                        content=Replies.user_not_in_vc_msg)

        reply_msg:discord.Message = None

        #Play again button                   
        if btn:
            #Supress the interaction failed message  
            await btn.edit_origin(content=btn.message.content)
            reply_msg = await ctx.reply(content=f"🎻 {btn.author.mention} requests to play this song again")
      
        else:
            #URL
            if query.startswith("https://"):
                if query.startswith("https://www.youtube.com/watch?v="): 
                    reply_msg = await ctx.send(f"{Emojis.YOUTUBE_ICON} A Youtube link is selected")
                    
                #Not youtube video link
                else:
                    return await ctx.send("💿 Sorry ! But only Youtube video links can be played !")

            #Favourites
            elif 'fav' in query.lower():
                from re import findall
                try:
                    index = int(findall(r'\d+', query)[0])
                    _,link = Favourties.get_track_by_index(author, index-1)
                    query = link
                except (ValueError,IndexError):
                    return await ctx.reply("❌ Failed to get song from your favourite list")
                else:
                    reply_msg = await ctx.send(f"🎧 Track **#{index}** in {author.mention}'s favourites has been selected")
                        
            #Keyword
            else:
                #Searching
                searchResult = super().search_from_youtube(query)

                if not searchResult:
                    return await ctx.reply("An error hass been captured when searching for the audio ! ( Try again )")

                #Add the buttons and texts for user to see
                choicesString:str = ""
                choicesButtons = []
                
                for i in range(5):
                    video = searchResult[i]
                    title = video["title"]["runs"][0]["text"]
                    length = video["lengthText"]["simpleText"]
                    choicesString += f'{i+1}: {title} `[{length}]`\n'

                    choicesButtons.append(Button(label=str(i+1),
                                                custom_id=str(i),
                                                style=ButtonStyle.blue))
                
                #Send those buttons and texts
                choicesMsg = await ctx.send(embed=discord.Embed(title="🎵  Select a song you would like to play : ( click the buttons below )",
                                                                description=choicesString,
                                                                color=discord.Color.from_rgb(255, 255, 255) ),
                                            components=[choicesButtons])
                
                #Get which button user pressed
                try:
                    choicesInteraction = await self.bot.wait_for("button_click",
                                                                timeout=TimeOutSeconds,
                                                                check=lambda btn: btn.author == author and btn.message.id == choicesMsg.id)
                #Not pressed for ammount of time
                except asyncio.TimeoutError:
                    return await choicesMsg.edit(embed=Embeds.NoTrackSelectedEmbed,
                                                components=[])
                #Received option
                else:
                    try:
                        index = int(choicesInteraction.custom_id)
                        await choicesInteraction.edit_origin(content=f"{Emojis.YOUTUBE_ICON} Song **#{index+1}** in the youtube search result has been selected",
                                                            components = [])
                        reply_msg = await ctx.fetch_message(choicesMsg.id)
                        query = f'https://www.youtube.com/watch?v={searchResult[index]["videoId"]}'
                    except ValueError:
                        print("Value error")
              
        
        queue = self.get_queue(guild)
        #------
        #Stop current audio (if queuing is disabled)
        if guild.voice_client and not queue.enabled:
            guild.voice_client.stop()
        #Join Voice channel
        elif author.voice:
            await super().join_voice_channel(guild=guild,
                                             vc=author.voice.channel)

        #Create the track
        try:
            NewTrack:SongTrack = await self.bot.loop.run_in_executor(None,
              lambda: SongTrack.create_track(query=query,
                                             requester=author))
        #Failed
        
        except BaseException as expection:
            await Logging.log(f"an error captured when trying to get info from `{query}` : {expection} ;")
            await ctx.send(f" Failed to play track `{query}`, reason is :\n`{str(expection).replace('ERROR: ','')}`")
        #Success
        else:
            
            queue.append(NewTrack)
            

            if queue.get(1) is not None:
                # track_repeated:bool = any([True for track in queue[1:] if track.webpage_url == NewTrack.webpage_url])
                # if track_repeated:
                #     await reply_msg.edit(reply_msg.content + "(A)")
                #     # return await ctx.reply("This song is already in the queue")
                await reply_msg.edit(embed=discord.Embed(title = f"\"{NewTrack.title}\" has been added to the queue",
                                                         color=discord.Color.from_rgb(255, 255, 255))
                                              .add_field(name="Length ↔️",
                                                         value=f"`{Convert.length_format(NewTrack.duration)}`")
                                              .add_field(name = "Position in queue 🔢",
                                                         value=len(queue)-1)
                                          .set_thumbnail(url = NewTrack.thumbnail)
                                    )
                if self.is_playing(guild):
                    return
                    
                reply_msg = reply_msg.channel

                NewTrack = queue[0]
            
            #Repeat function after the audio
            start_time = float(time.perf_counter())
            after_playing = lambda voice_error: self.after_playing(guild,start_time,voice_error)

            #Play the audio

            NewTrack.play(guild.voice_client,
                          volume = self.get_volume(guild),
                          after= after_playing)
            
            await self.create_audio_message(NewTrack,reply_msg)
#----------------------------------------------------------------#
#QUEUE
    @commands.guild_only()
    @commands.group(description="Access the queue commands",
                    aliases = ["que","qeueu","q"])
    async def queue(self,ctx):
        await Logging.log(f"{ctx.author} used queue command : {ctx.subcommand_passed} in [{ctx.guild}] ;")
        
        if not self.get_queue(ctx.guild).enabled:
            raise error_type.QueueDisabled

        if ctx.invoked_subcommand is None:

            def get_params_str(cmd)->str:
                if list(cmd.clean_params):
                    return f"`[{']` `['.join(list(cmd.clean_params))}]`"
                return ""


            await ctx.reply(embed=discord.Embed(
                title = "Queue commands :",
                description = "\n".join([f"{ctx.prefix}queue **{cmd.name}** {get_params_str(cmd)}" for cmd in ctx.command.walk_commands() ]),
                color = discord.Color.from_rgb(255,255,255)
              ) 
            )

    @commands.guild_only()
    @queue.command(description="Display tracks in the song queue",
                   aliases=["show","songs","tracks"])
    async def display(self,ctx):
      queue = self.get_queue(ctx.guild)

      if len(queue) ==0: 
          raise error_type.QueueEmpty
      
      symbol = "▶︎" if not self.is_paused(ctx.guild) else "\\⏸"
      await ctx.send(embed = 
      discord.Embed(title = f"🎧 Current Queue | Track Count : {len(queue)} | Full Length : {Convert.length_format(queue.total_length)} | Repeat queue : {Convert.bool_to_str(queue.queue_looping)} ",
                    description = "\n".join([f"**{f'[ {i} ]' if i > 0 else f'[{symbol}]'}** {track.title}\
                        \n> `{Convert.length_format(track.duration)}` | {track.requester.mention}" for i,track in enumerate(list(queue))]),
                    color=discord.Color.from_rgb(255, 255, 255),
                    timestamp=datetime.now()
        )
      )

    @commands.guild_only()
    @queue.command(description="Remove a track from the queue",
                   aliases=["delete","del"])
    async def remove(self,ctx,position):
        queue = self.get_queue(ctx.guild)

        if len(queue) ==0:
            raise error_type.QueueEmpty

        try:
            position = int(position)
            if position ==0 and ctx.voice_client.source:
                raise IndexError("Cannot remove current song")
            poped_track = queue.get(position)

            queue.pop(position)
        except (TypeError,IndexError) as e:
            await ctx.reply(f"❌ Invaild position, {e}")
        else:
            await ctx.reply(f"**#{position}** - `{poped_track.title}` has been removed from the queue")
    
    @commands.guild_only()
    @queue.command(description="Removes every track in the queue",
                   aliases=["empty","clr"],)
    async def clear(self,ctx):
        queue:SongQueue = self.get_queue(ctx.guild)

        queue.audio_control_status = "CLEAR"
        queue.clear()
        await self.clear_audio_message(ctx.guild)
        if ctx.voice_client:
            ctx.voice_client.stop()

        await ctx.reply("🗒 The queue has been cleared")

    @commands.guild_only()
    @queue.command(description="Swap the position of two tracks in the queue")
    async def swap(self,ctx,position_1,position_2):
        queue = self.get_queue(ctx.guild)

        try:
            queue.swap(position_1,position_2)
        except (TypeError,IndexError):
            await ctx.reply("❌ Invaild position")
        else:
            await ctx.reply(f"Swapped **#{position_1}** with **#{position_2}** in the queue")

    @commands.guild_only()
    @queue.command()
    async def reverse(self,ctx):
        queue:SongQueue = self.get_queue(ctx.guild)
        playing:SongTrack = queue.popleft()
        queue.reverse()
        queue.appendleft(playing)

        await ctx.reply("🔃 The queue has been *reversed*")

    @commands.guild_only()
    @queue.command(description="Randomize the position of every track in the queue",
                   aliases = ["shuffle_queue","random","randomize","sfl"],)
    async def shuffle(self,ctx):
        queue = self.get_queue(ctx.guild)
        queue.shuffle()

        await ctx.reply("🎲 The queue has been *shuffled*")

    @commands.guild_only()
    @queue.command(description='🔂 Enable / Disable queue looping.\nWhen enabled, tracks will be moved to the last at the queue after finsh playing',
                   aliases=["loop","looping","repeat_queue",'setloop','setlooping',"toggleloop","toggle_looping",'changelooping','lop'],)
    async def repeat(self,ctx,mode=None):
        guild = ctx.guild

        queue = self.get_queue(guild)
        new_qloop = queue.queue_looping
            
        #if not specified a mode
        if not mode:
            new_qloop = not new_qloop
        else:
            new_qloop = Convert.str_to_bool(mode)
            if new_qloop is None:
                return await ctx.reply(Replies.invaild_mode_msg)
        

        queue.queue_looping = new_qloop
        await ctx.reply(Replies.queue_loop_audio_msg.format(Convert.bool_to_str(self.get_queue_loop(guild))))

#----------------------------------------------------------------#
#Voice update
    @commands.Cog.listener()
    async def on_voice_state_update(self,member, before, after):
        channel = before.channel or after.channel
        guild = channel.guild
        voice_client = guild.voice_client

        if not voice_client: 
            return 

        #If it is a user leaving a vc
        if not member.bot and before.channel and before.channel != after.channel: 
            #The bot is in that voice channel that the user left
            if guild.me in before.channel.members:
                #And no one is in the vc anymore
                if not self.get_non_bot_vc_members(guild):
                    print("Nobody is in vc with me")

                    #Pause if it's playing stuff
                    try:
                        channel = self.get_queue(guild).audio_message.channel
                        await channel.send(f"⏸ Paused since nobody is in {before.channel.mention} ( leaves after 30 seconds )",
                                            delete_after=30)
                        voice_client.pause()
                    except AttributeError: 
                        pass
                    
                    #Leave the vc if after 30 second still no one is in vc
                    await asyncio.sleep(30)
                    if voice_client and not self.get_non_bot_vc_members(guild):
                        await voice_client.disconnect()
        #---------------------#
        #Bot moved channel
        elif member == self.bot.user:
            if before.channel and after.channel:
                if before.channel.id != after.channel.id: #Moving channel
                    if voice_client:
                        print("Pasued because moved")
                        guild.voice_client.pause()

#Button detecting
    @commands.Cog.listener()
    async def on_button_click(self, btn):
        guild = btn.guild

        await Logging.log(f"{btn.author} pressed `{btn.custom_id}` button in [{guild if guild else 'DM'}] ;")
        
        if btn.responded or guild is None:  return
        
        queue = self.get_queue(guild)

        #Buttons
        if btn.custom_id == Buttons.FavouriteButton.custom_id:
            await super().on_favourite_btn_press(btn)

        elif btn.custom_id == Buttons.PlayAgainButton.custom_id:
            await super().on_play_again_btn_press(btn)

        #Clearing glitched messages
        elif queue.get(0) is None or queue.audio_message is None or queue.audio_message.id != btn.message.id or not self.is_playing(guild):
            if not btn.custom_id.isnumeric() and not btn.responded and btn.message.embeds:
                new_embed:discord.Embed = btn.message.embeds[0]
                if len(new_embed.fields) == 6:
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
            await super().update_audio_msg(guild)
        elif btn.custom_id == Buttons.RestartButton.custom_id:
            await super().on_restart_btn_press(btn)
        elif btn.custom_id == Buttons.SkipButton.custom_id:
            await super().on_skip_btn_press(btn)
#----------------------------------------------------------------#
#Now playing

    @commands.guild_only()
    @commands.command(aliases=["np", "nowplaying", "now"],
                      description='🔊 Display the current audio playing in the server')
    async def now_playing(self, ctx:commands.Context):
        await Logging.log(f"{ctx.author} used now playing command in [{ctx.guild}] ;")

        queue = self.get_queue(ctx.guild)
        audio_message:discord.Message = queue.audio_message
        #No audio playing (not found the now playing message)
        if audio_message is None:
            return await ctx.reply(Replies.free_to_use_msg)
        elif ctx.voice_client is None:
            return await ctx.reply(Replies.free_to_use_msg + "| not in a voice channel")

        #if same text channel
        if audio_message.channel == ctx.channel:
            return await audio_message.reply("*🎧 This is the audio playing right now ~*")
        #Or not
        await ctx.send(f"🎶 Now playing in {self.get_current_vc(ctx.guild).mention} - **{queue[0].get('title')}**")
#----------------------------------------------------------------#
#Favourites

    @commands.guild_only()
    @commands.command(aliases=['addtofav', "save", "savesong", "fav"],
                      description='👍🏻 Add the current song playing to your favourites')
    async def favourite(self, ctx:commands.Context):
        #No audio playing
        if not self.is_playing(ctx.guild):
            return await ctx.reply(Replies.free_to_use_msg)

        Track = self.get_queue(ctx.guild)[0]

        await Logging.log(f"`{ctx.author}` added `[{Track.title}]` to the fav list in [{ctx.guild}] ;")

        #Add to the list
        Favourties.add_track(ctx.author, Track.title, Track.webpage_url)

        #Responding
        await ctx.reply(Replies.added_fav_msg.format(Track.title))

#Unfavouriting song

    @commands.command(aliases=['unfav', 'removefromfav'],
                      description='❣🗒 Remove a song from your favourites')
    async def unfavourite(self, ctx:commands.Context, index):
        await Logging.log(f"`{ctx.author}` removed `[{index}]` from the fav list in [{ctx.guild}] ;")
        try:
            from re import findall
            index = int(findall(r'\d+', index)[0]) - 1
            removedTrackTitle = Favourties.get_track_by_index(ctx.author,index)[0]
            Favourties.remove_track(ctx.author,index)
        except (IndexError,ValueError):
            await ctx.reply("✏ Please enter a vaild index")
        except FileNotFoundError:
            await ctx.reply(Replies.fav_empty_msg)
        else: 
            await ctx.reply(f"`{removedTrackTitle}` has been removed from your favourites")
        
#Display Favourites

    @commands.command(aliases=[
        'showfav', "favlist", "myfavourites", "myfavourite", "myfavs", "myfav"
    ],
                      description='❣🗒 Display every song in your favourites')
    async def display_favourites(self, ctx:commands.Context):
      await Logging.log(f"{ctx.author} used display_favourites command in [{ctx.guild}] ;")

      #Grouping the list in string
      try:
          favs_list = Favourties.get_data(ctx.author)
      except FileNotFoundError:
          return await ctx.reply(Replies.fav_empty_msg)

      wholeList = ""
      for index, title in enumerate(favs_list):
          wholeList += "***{}.*** {}\n".format(index + 1,title)

      #embed =>
      favouritesEmbed = discord.Embed(title=f"🤍 🎧 Favourites of {ctx.author.name} 🎵",
                                      description=wholeList,
                                      color=discord.Color.from_rgb(255, 255, 255),
                                      timestamp=datetime.now()
                        ).set_footer(text="Your favourites would be the available in every server")

      #sending the embed
      await ctx.reply(embed=favouritesEmbed)

#----------------------------------------------------------------#
def setup(BOT):
    BOT.add_cog(music_commands(BOT))