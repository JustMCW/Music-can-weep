#Built-ins
from functools import reduce
import asyncio
import time
import re
import os
from datetime import datetime

#Third party libary
import discord
from discord.ext import commands

#My own libary
from log import Logging
from main import BOT_INFO
import Convert

import Favourites
from subtitles import Subtitles

from Music.queue import SongQueue
from Music.song_track import SongTrack
from Music import VoiceState

from Buttons import Buttons
#Literals
from Response import MessageString,Emojis,Embeds


#----------------------------------------------------------------#

#Btn message sent and delete after
time_out_seconds:int = 60 * 2
initial_volume:float = BOT_INFO.InitialVolume


#----------------------------------------------------------------#


#Search Audio fromm Youtube
def search_from_youtube(query:str, 
                        ResultLengthLimit:int=5,
                        DurationLimit:int=3*3600) -> list:
    """
    Search youtube videos with a given string
    """
    from requests import get
    from bs4 import BeautifulSoup
    from json import loads

    #Send the request and grab the html text
    httpResponse = get(f"https://www.youtube.com/results?search_query={'+'.join(word for word in query.split())}")
    htmlSoup = BeautifulSoup(httpResponse.text, "lxml")

    #Fliter the html soup ( get rid of other elements such as the search bar and side bar )
    scripts = [s for s in htmlSoup.find_all("script") if "videoRenderer" in str(s)][0]

    #Find the data we need among the scripts, and load it into json
    JsonScript = re.search('var ytInitialData = (.+)[,;]{1}',str(scripts)).group(1)
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
                if int(re.search(r"(.*) hours", longText).group(1)) > DurationLimit: 
                    continue
            FilteredQueryList.append(VidRend)
            
            #Result length
            if len(FilteredQueryList) >= ResultLengthLimit: 
                break

    return FilteredQueryList 

    
#----------------------------------------------------------------#

#COMMANDS
class music_commands\
(
  commands.Cog, 

):
    def __init__(self,bot):
        print("MUSIC commands is ready")

        self.bot:commands.Bot = bot

        super().__init__()

#CHANGING BOT'S VOICE CHANNEL
    @commands.bot_has_guild_permissions(connect=True, speak=True)
    @commands.command(aliases=["enter", "j"],
                    description='🎧 Connect to your current voice channel or a given voice channel name',
                    usage = "{}join Music channel")
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
            raise commands.errors.UserNotInVoiceChannel
        else:
            channel_to_join = author.voice.channel

        #if already in the that same voice channel
        if ctx.voice_client:
            if channel_to_join == ctx.voice_client.channel:
                return await ctx.reply(MessageString.same_vc_msg.format(channel_to_join.mention))

        #Join
        await VoiceState.join_voice_channel(ctx.guild, channel_to_join)

        #Response
        await ctx.reply(MessageString.join_msg.format(channel_to_join.mention))
        await Logging.log(f"{author} just make me joined `{channel_to_join}` in [{ctx.guild}] ;")
        await VoiceState.update_audio_msg(ctx.guild)

    @commands.guild_only()
    @commands.command(aliases=["leave", "bye", 'dis', "lev",'l'],
                    description='👋 Disconnect from the current voice channel i am in',
                    usage="{}leave")
    async def disconnect(self, ctx:commands.Context):
        voice_client = ctx.voice_client

        #Not in a voice voice_client
        if not voice_client: 
            raise commands.errors.NotInVoiceChannel

        #Disconnect from voice_client
        await voice_client.disconnect()

        #Message
        await ctx.reply(MessageString.leave_msg.format(voice_client.channel.mention))
        await Logging.log(f"{ctx.author} just make me disconnect from `{voice_client.channel}` in [{ctx.guild}] ;")

#----------------------------------------------------------------#
#INTERRUPTING THE AUDIO

    @commands.guild_only()
    @commands.command(aliases=["wait"],
                      description='⏸ Pause the current audio',
                      usage="{}pause")
    async def pause(self, ctx:commands.Context):
        
        VoiceState.pause_audio(ctx.guild)

        await ctx.reply(MessageString.paused_audio_msg)
        await Logging.log(
            f"{ctx.author} used pause command in [{ctx.guild}] ;"
        )

    @commands.guild_only()
    @commands.command(aliases=["continue", "unpause"],
                      description='▶️ Resume the current audio',
                      usage="{}resume")
    async def resume(self, ctx:commands.Context):
        guild = ctx.guild
        queue:SongQueue = guild.song_queue      

        #Not playing anything but the queue has something
        if queue.get(0) is not None:
            try:
                VoiceState.resume_audio(guild)       
            except (commands.errors.NotInVoiceChannel,commands.errors.NoAudioPlaying):

                if guild.voice_client is None:
                    try:
                        await VoiceState.join_voice_channel(guild, ctx.author.voice.channel)
                    except AttributeError:
                        raise commands.errors.NotInVoiceChannel
                
                self.bot.loop.create_task(Subtitles.sync_subtitles(queue,ctx.channel,queue[0]))

                #Repeat function after the audio
                start_time = float(time.perf_counter())

                #Play the audio
                queue[0].play(guild.voice_client,
                              volume = queue.volume,
                              after = lambda voice_error: VoiceState.after_playing(self.bot.loop,
                                                                            guild,
                                                                            start_time,
                                                                            voice_error)
                            )

                continue_playing_queue_msg = await ctx.send("▶️ Continue to play tracks in the queue")
                await VoiceState.create_audio_message(queue[0],continue_playing_queue_msg)
            else:
                await ctx.reply(MessageString.resumed_audio_msg)
        else:
            VoiceState.resume_audio(guild)
            await ctx.reply(MessageString.resumed_audio_msg)
        
        await Logging.log(f"{ctx.author} used resume command in [{ctx.guild}] ;")

    @commands.guild_only()
    @commands.command(aliases=["fast_forward","fwd"],
                      description = "⏭ Fast-foward the time position of the current audio for a certain amount of time.",
                      usage="{0}fwd 10\n{0}foward 10:30")
    async def forward(self,ctx,*,time:str):
        voicec:discord.VoiceClient = ctx.voice_client
        if not voicec.is_playing():
            raise commands.errors.NoAudioPlaying
        
        guild = ctx.guild

        queue = guild.song_queue
        fwd_sec:float = Convert.time_to_sec(time)

        await ctx.trigger_typing()
        if queue[0].duration < (fwd_sec+queue.time_position):
            await ctx.reply("Ended the current track")
            return voicec.stop()
        VoiceState.pause_audio(guild)

        for _ in range(fwd_sec * 50):
            try:
                voicec.source.read()
            except AttributeError:
                break
        queue.player_loop_passed.append(fwd_sec * 50)
        VoiceState.resume_audio(guild)
        await ctx.reply(f"*⏭ Fast-fowarded for {Convert.length_format(fwd_sec)} seconds*")

    @commands.guild_only()
    @commands.command(aliases=["jump"],
                      description="⏏️ Move the time position of the current audio, format : [Hours:Minutes:Seconds] or literal seconds like 3600 (an hour). This is a experimental command.",
                      usage="{}seek 2:30")
    async def seek(self,ctx:commands.Context,*,time_position):

        try:
            position_sec:float = Convert.time_to_sec(time_position)
            VoiceState.restart_audio(ctx.guild,position=position_sec)
        except ValueError:
            await ctx.reply(f"Invaild time position, format : {ctx.prefix}{ctx.invoked_with} [Hours:Minutes:Seconds]")
        except IndexError:
            await ctx.voice_client.stop()
        else:
            await ctx.reply(f"⏏️ Moving audio's time position to `{Convert.length_format(position_sec)}` (It might take a while depend on the length of the audio)")

    @commands.guild_only()
    @commands.command(aliases=["previous"],
                      description="⏪ Return to the last song played",
                      usage="{}previous")
    async def last(self, ctx:commands.Context):

        VoiceState.rewind_audio(ctx.guild)

        await ctx.reply(MessageString.rewind_audio_msg)
        await Logging.log(f"{ctx.author} used rewind command in [{ctx.guild}] ;")

    @commands.guild_only()
    @commands.command(aliases=["next"],
                      description='⏩ skip to the next audio in the queue',
                      usage="{}skip")
    async def skip(self, ctx:commands.Context):
        
        VoiceState.skip_audio(ctx.guild)

        await ctx.reply(MessageString.skipped_audio_msg)
        await Logging.log(f"{ctx.author} used skip command in [{ctx.guild}] ;")


    @commands.guild_only()
    @commands.command(description='⏹ stop the current audio from playing 🚫',
                      usuge="{}stop")
    async def stop(self, ctx:commands.Context):

        #Checking
        if not ctx.voice_client:
            raise commands.errors.NotInVoiceChannel
        if not ctx.voice_client.is_playing():
            raise commands.errors.NoAudioPlaying
        
        await ctx.voice_client.disconnect()

        await ctx.reply(MessageString.stopped_audio_msg)

        await Logging.log(f"{ctx.author} used stop command in [{ctx.guild}] ;")

    @commands.guild_only()
    @commands.command(aliases=["replay", "re"],
                      description='🔄 restart the current audio track',
                      usage="{}replay")
    async def restart(self, ctx:commands.Context):

        VoiceState.restart_audio(ctx.guild)

        await ctx.reply(MessageString.restarted_audio_msg)
        await Logging.log(f"{ctx.author} used restart command in [{ctx.guild}] ;")
#----------------------------------------------------------------#

    @commands.guild_only()
    @commands.command(aliases=["vol"],
                    description='📶 set audio volume to a percentage (0% - 200%)',
                    usage="{}vol 70")
    async def volume(self, ctx:commands.Context, volume_to_set):

        #Try getting the volume_percentage from the message
        try:
            volume_percentage = float(re.findall(r"\d+",volume_to_set)[0])
        except IndexError:
            return await ctx.reply("🎧 Please enter a vaild volume percentage 🔊")
        await Logging.log(f"{ctx.author} set volume to `{round(volume_percentage,2)}%` in [{ctx.guild}] ;")

        PERCENTAGE_LIMIT = 200
        
        #Volume higher than limit
        if volume_percentage > PERCENTAGE_LIMIT and ctx.author.id != self.bot.owner_id:
            return await ctx.reply(f"🚫 Please enter a volume below {PERCENTAGE_LIMIT}% (to protect yours and other's ears 👍🏻)")

        #Setting the actual volume we are going to set
        true_volume = volume_percentage / 100 * initial_volume
        
        ctx.guild.song_queue.volume = true_volume

        await VoiceState.update_audio_msg(ctx.guild)
        vc = ctx.voice_client
        if vc and vc.source:
            vc.source.volume = true_volume
            
        await ctx.reply(f"🔊 Volume has been set to {round(volume_percentage,2)}%")

    @commands.guild_only()
    @commands.command(aliases=["looping","repeat"],
                      description='🔂 Enable / Disable single audio track looping\nWhen enabled tracks will restart after playing',
                      usage="{}loop on")
    async def loop(self, ctx:commands.Context, mode=None):
        guild = ctx.guild
      
        new_loop = guild.song_queue.looping

        #if not specified a mode
        if not mode:
          new_loop = not new_loop
        else:
          new_loop = Convert.str_to_bool(mode)
          if new_loop is None:
            return await ctx.reply(MessageString.invaild_mode_msg)

        guild.song_queue.looping = new_loop

        await ctx.reply(MessageString.loop_audio_msg.format(Convert.bool_to_str(new_loop)))
        await VoiceState.update_audio_msg(guild)

        await Logging.log(f"{ctx.author} set loop to `{new_loop}` in [{guild}] ;")
        
#----------------------------------------------------------------#
#Playing audio

    @commands.bot_has_guild_permissions(connect=True, speak=True)
    @commands.command(aliases=["p","music"],
                    description='🔎 Search and play audio with a given YOUTUBE link or from keywords 🎧',
                    usage="{0}play https://www.youtube.com/watch?v=GrAchTdepsU\n{0}p mood\n{0}play fav 4"
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
                raise commands.errors.UserNotInVoiceChannel
            else:
                return await btn.respond(type=4,
                                        content=MessageString.user_not_in_vc_msg)

        reply_msg:discord.Message = None

        #Play again button                   
        if btn:
            #Supress the interaction failed message  
            await btn.edit_origin(content=btn.message.content)
            reply_msg = await ctx.reply(content=f"🎻 {btn.author.mention} requests to play this song again")
      
        else:
            #URL
            youtube_link_match_result = re.findall(r"(https|HTTP)://(youtu\.be|www.youtube.com)(/shorts)?/(watch\?v=)?([A-Za-z0-9\-_]{11})",query)
            
            if "https://" in query or "HTTP://" in query:
                #Not youtube video link
                if youtube_link_match_result: 
                #     pass
                #     return await ctx.send("💿 Sorry ! But only Youtube video links can be played !")
                # else:
                    query = "https://www.youtube.com/watch?v="+youtube_link_match_result[0][4]

                    reply_msg = await ctx.send(f"{Emojis.YOUTUBE_ICON} A Youtube link is selected")
                elif "soundcloud.com" in query:

                    reply_msg = await ctx.send(f"☁️ A Soundcloud link is selected")
                else:
                    return await ctx.send("Sorry ! Only Youtube and Soundcloud links are supported ! (Spotify will be added soon)")

            #Favourites
            elif 'fav' in query.lower():
                try:
                    index = int(re.findall(r'\d+', query)[0])
                    _,link = Favourites.get_track_by_index(author, index-1)
                    query = link
                except (ValueError,IndexError):
                    return await ctx.reply("❌ Failed to get song from your favourite list")
                else:
                    reply_msg = await ctx.send(f"🎧 Track **#{index}** in {author.mention}'s favourites has been selected")
                        
            #Keyword
            else:
                #Searching
                try:
                    search_res:list = search_from_youtube(query,ResultLengthLimit=100)
                except IndexError:
                    return await ctx.reply("No search result was found for that ...")

                #Add the buttons and texts for user to see
                choicesString:str = ""
                choicesButtons = []

                gen = Buttons.generate_search_result_buttons(search_res)
                
                for _ in range(5):
                    add_str,add_button = next(gen)
                    choicesString +=  add_str + "\n"
                    choicesButtons.append(add_button)
                print(list(gen))
                #Send those buttons and texts
                choicesMsg = await ctx.send(embed=discord.Embed(title="🎵  Select a song you would like to play : ( click the buttons below )",
                                                                description=choicesString,
                                                                color=discord.Color.from_rgb(255, 255, 255) ),
                                            components=[choicesButtons])
                
                #Get which button user pressed
                try:
                    choicesInteraction = await self.bot.wait_for("button_click",
                                                                timeout=time_out_seconds,
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
                        query = f'https://www.youtube.com/watch?v={search_res[index]["videoId"]}'
                    except ValueError:
                        print("Value error")
              
        
        queue = guild.song_queue
        #------
        
        #Create the track
        try:
            NewTrack:SongTrack = await self.bot.loop.run_in_executor(None,
              lambda: SongTrack.create_track(query=query,
                                             requester=author))
        #Failed
        
        except BaseException as expection:
            print(expection)
            if "Unsupported URL" in str(expection):
                return await ctx.reply("Sorry, this url is not supported !")
            
            error_dict:dict = {
                "Sign in to confirm your age":"Youtube has marked this video as inappropriate content.",
                "Unable to recognize tab page":"the video link was invalid, please double check it.",
                "Video unavailable":expection,
                "requested format not available":"Live stream cannot be played.",
                "No video formats found":"429 too many request, this error has been reported automatically."
            }
            await Logging.log(f"An error captured when trying to gather infomation from `{query}` :\n{expection} ;")
            for error_msg,reply in error_dict.items():
                if error_msg in str(expection):
                    if "429" in reply:
                        await Logging.error("429 429 429 429 429 429 429 429 <@812808602997620756>")
                    return await ctx.send(f"Unable to play track `{query}` because {reply}")
            await Logging.error(f"BIG BIG BIG ERROR : {expection}")

        #Success
        else:
            print("Succesfully extraced info")
            #Stop current audio (if queuing is disabled)
            if guild.voice_client and not queue.enabled:
                guild.voice_client.stop()
            #Join Voice channel
            elif author.voice:
                await VoiceState.join_voice_channel(guild=guild,
                                                 vc=author.voice.channel)

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
                if VoiceState.is_playing(guild):
                    return

                reply_msg = ctx.channel
                NewTrack = queue[0]

            #Repeat function after the audio
            start_time = float(time.perf_counter())

            self.bot.loop.create_task(Subtitles.sync_subtitles(queue,ctx.channel,NewTrack))
            #Play the audio
            try:
                NewTrack.play(guild.voice_client,
                            volume = queue.volume,
                            after= lambda voice_error: VoiceState.after_playing(self.bot.loop,
                                                                          guild,
                                                                          start_time,
                                                                          voice_error))
            except discord.errors.ClientException as CE:
                print(CE)
                if queue.enabled:
                    await reply_msg.edit(embed=discord.Embed(title = f"\"{NewTrack.title}\" has been added to the queue",
                                            color=discord.Color.from_rgb(255, 255, 255))
                                .add_field(name="Length ↔️",
                                            value=f"`{Convert.length_format(NewTrack.duration)}`")
                                .add_field(name = "Position in queue 🔢",
                                            value=len(queue)-1)
                            .set_thumbnail(url = NewTrack.thumbnail))
                else:
                    await ctx.reply("Unable to play this track because another tracks was requested at the same time")
            else:
                await VoiceState.create_audio_message(NewTrack,reply_msg or ctx.channel)
            


#----------------------------------------------------------------#
#QUEUE
    @commands.guild_only()
    @commands.group(description="🔧 You can manage the song queue with this group of command",
                    aliases = ["que","qeueu","q"],
                    usage="{0}queue display\n{0}q clear")
    async def queue(self,ctx):
        await Logging.log(f"{ctx.author} used queue command : {ctx.subcommand_passed} in [{ctx.guild}] ;")
        
        if not ctx.guild.song_queue.enabled:
            raise commands.errors.QueueDisabled

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
    @queue.command(description="📋 Display tracks in the song queue",
                   aliases=["show"],
                   usage="{}queue display")
    async def display(self,ctx):
      queue = ctx.guild.song_queue

      if len(queue) ==0: 
          raise commands.errors.QueueEmpty
      
      symbol = "▶︎" if not VoiceState.is_paused(ctx.guild) else "\\⏸"
      await ctx.send(embed = 
      discord.Embed(title = f"🎧 Queue | Track Count : {len(queue)} | Full Length : {Convert.length_format(queue.total_length)} | Repeat queue : {Convert.bool_to_str(queue.queue_looping)}",
                    description = "\n".join([f"**{f'[ {i} ]' if i > 0 else f'[{symbol}]'}** {track.title}\
                        \n> `{Convert.length_format(track.duration)}` | {track.requester.mention}" for i,track in enumerate(list(queue))]),
                    color=discord.Color.from_rgb(255, 255, 255),
                    timestamp=datetime.now()
        )
      )

    @commands.guild_only()
    @queue.group(description=" Remove one song track by position in the queue, or remove all song tracks that apply to the statement ",
                aliases=["rm","delete","del"],
                usage="{0}queue remove 1\n{0}q rm dup")
    async def remove(self,ctx:commands.Context):
        
        queue = ctx.guild.song_queue

        if len(queue) ==0:
            raise commands.errors.QueueEmpty

        if ctx.invoked_subcommand is None:     

            position:str = ctx.subcommand_passed

            if not position:
                raise commands.errors.MissingRequiredArgument("position")

            try:
                position:int = int(re.findall(r"\d+",position)[0])

                if position ==0 and ctx.voice_client.source:
                    raise IndexError("Cannot remove current song")
                poped_track = queue.get(position)

                queue.pop(position)
            except (TypeError,IndexError) as e:

                await ctx.reply(f"❌ Invaild position")
            else:
                await ctx.reply(f"**#{position}** - `{poped_track.title}` has been removed from the queue")
        
    
    @commands.guild_only()
    @remove.command(description="Remove tracks which are duplicated in the queue",
                    aliases=["dup","repeated"],
                    usage="{}queue remove duplicate")
    async def duplicated(self,ctx):

        queue:SongQueue = ctx.guild.song_queue

        not_rep = []

        def is_dup(appeared:list,item:SongTrack):
            if item.webpage_url not in appeared:
                appeared.append(item.webpage_url)
                not_rep.append(item)
            return appeared
        
        reduce(is_dup,queue,[])
        removed_index:int = len(queue) - len(not_rep)

        if removed_index == 0:
            print(not_rep)
            return await ctx.reply("No track is repeated !")

        queue.clear()
        queue.extend(not_rep)

        await ctx.reply(f"Successfully removed `{removed_index}` duplicated tracks from the queue.")
    
    @commands.guild_only()
    @remove.command(description="Remove tracks which their requester is not in the bot's voice channel",
                    aliases=["left_vc","left"],
                    usage="{}queue remove left")
    async def left_user(self,ctx:commands.Context):
        
        queue = ctx.guild.song_queue
        
        user_in_vc:list[discord.Member] = VoiceState.get_non_bot_vc_members()
        user_in_vc_ids:list[int] = map(lambda mem:mem.id, user_in_vc)

        in_vc = filter(lambda t: t.requester.id in user_in_vc_ids, queue)

        remove_count = len(queue) - len(in_vc)
        if remove_count == 0:
            return await ctx.reply("No track is removed !")

        queue.clear()
        queue.extend(in_vc)

        await ctx.reply(f"Successfully removed {remove_count} tracks from the queue.")

    @commands.guild_only()
    @queue.command(description="🧹 Removes every track in the queue",
                   aliases=["empty","clr"],
                   usage="{}queue clear")
    async def clear(self,ctx):
        queue:SongQueue = ctx.guild.song_queue

        queue.audio_control_status = "CLEAR"
        queue.clear()
        await VoiceState.clear_audio_message(ctx.guild)
        if ctx.voice_client:
            ctx.voice_client.stop()

        await ctx.reply("🗒 The queue has been cleared")

    @commands.guild_only()
    @queue.command(description="🔁 Swap the position of two tracks in the queue",
                   usage="{}queue swap 1 2")
    async def swap(self,ctx,position_1,position_2):
        queue = ctx.guild.song_queue

        try:
            queue.swap(position_1,position_2)
        except (TypeError,IndexError):
            await ctx.reply("❌ Invaild position")
        else:
            await ctx.reply(f"Swapped **#{position_1}** with **#{position_2}** in the queue")

    @commands.guild_only()
    @queue.command(description="🔃 Reverse the position of the whole queue",
                    usage="{}queue reverse")
    async def reverse(self,ctx):
        queue:SongQueue = ctx.guild.song_queue
        playing:SongTrack = queue.popleft()
        queue.reverse()
        queue.appendleft(playing)

        await ctx.reply("🔃 The queue has been *reversed*")

    @commands.guild_only()
    @queue.command(description="🎲 Randomize the position of every track in the queue",
                   aliases = ["random","randomize","sfl"],
                   usage="{}queue shuffle")
    async def shuffle(self,ctx):
        queue = ctx.guild.song_queue
        queue.shuffle()

        await ctx.reply("🎲 The queue has been *shuffled*")

    @commands.guild_only()
    @queue.command(description='🔂 Enable / Disable queue looping.\nWhen enabled, tracks will be moved to the last at the queue after finsh playing',
                   aliases=["loop","looping","repeat_queue",'setloop','setlooping',"toggleloop","toggle_looping",'changelooping','lop'],
                   usage="{}queue repeat on")
    async def repeat(self,ctx,mode=None):
        guild = ctx.guild

        queue = guild.song_queue
        new_qloop = queue.queue_looping
            
        #if not specified a mode
        if not mode:
            new_qloop = not new_qloop
        else:
            new_qloop = Convert.str_to_bool(mode)
            if new_qloop is None:
                return await ctx.reply(MessageString.invaild_mode_msg)
        

        queue.queue_looping = new_qloop
        await ctx.reply(MessageString.queue_loop_audio_msg.format(Convert.bool_to_str(guild.song_queue.queue_looping)))

#----------------------------------------------------------------#

    @commands.is_owner()
    @queue.command(description='Ouput the queue as a txt file, can be imported again through the import command')
    async def export(self,ctx:commands.Context):
        filename:str= f"q{ctx.guild.id}.txt"
        queue:SongQueue = ctx.guild.song_queue

        if not queue:
            raise commands.errors.QueueEmpty

        with open(filename,"x") as qfile:
            file_str:str = ""
            for track in queue:
                file_str += track.webpage_url + "\n"

            qfile.write(file_str)

        await ctx.send(file=discord.File(filename))

        os.remove(filename)

    @commands.is_owner()
    @queue.command(description='Input songs through a txt file, you can also export the current queue with queue export',
                   aliases=["import"],
                   usage="{}queue import [place your txt file in the attachments]")
    async def from_file(self,ctx:commands.Context):
        queue:SongQueue = ctx.guild.song_queue
        attach:discord.Attachment = ctx.message.attachments[0]
        if not attach:
            return await ctx.reply("Please upload a txt file")
        if "utf-8" in (attach.content_type):
            mes = await ctx.reply("This might take a while ...")
            data:list[str] = (await attach.read()).decode("utf-8").split("\n")

            for line in data:
                if line:
                    queue.append(await self.bot.loop.run_in_executor(None,
                                                                    lambda: SongTrack.create_track(query=line,
                                                                                                    requester=ctx.author)))
            await mes.edit(f"Successfully added {len(data)-1} tracks to the queue !")
        else:
            await ctx.reply("Invaild file type ! (txt and utf-8)")                       
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
                if not VoiceState.get_non_bot_vc_members(guild):
                    print("Nobody is in vc with me")

                    #Pause if it's playing stuff
                    try:
                        channel = guild.song_queue.audio_message.channel
                        await channel.send(f"⏸ Paused since nobody is in {before.channel.mention} ( leaves after 30 seconds )",
                                            delete_after=30)
                        voice_client.pause()
                    except AttributeError: 
                        pass
                    
                    #Leave the vc if after 30 second still no one is in vc
                    await asyncio.sleep(30)
                    if voice_client and not VoiceState.get_non_bot_vc_members(guild):
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

        from Buttons import Buttons

        guild = btn.guild

        await Logging.log(f"{btn.author} pressed `{btn.custom_id}` button in [{guild if guild else 'DM'}] ;")
        
        if btn.responded or guild is None:  return
        
        queue = guild.song_queue

        #Buttons
        if btn.custom_id == Buttons.FavouriteButton.custom_id:
            await Buttons.on_favourite_btn_press(btn)

        elif btn.custom_id == Buttons.PlayAgainButton.custom_id:
            await Buttons.on_play_again_btn_press(btn,self.bot)

        #Clearing glitched messages
        elif queue.get(0) is None or queue.audio_message is None or queue.audio_message.id != btn.message.id or not VoiceState.is_playing(guild):
            if not btn.custom_id.isnumeric() and not btn.responded and btn.message.embeds:
                new_embed:discord.Embed = btn.message.embeds[0]
                await btn.edit_origin(content=btn.message.content)
                if len(new_embed.fields) == 6:
                    await VoiceState.clear_audio_message(specific_message=btn.message)

        elif btn.custom_id == Buttons.SubtitlesButton.custom_id:
            await Buttons.on_subtitles_btn_press(btn,self.bot)
        elif btn.custom_id == Buttons.PauseButton.custom_id:
            await Buttons.on_pause_btn_press(btn)
        elif btn.custom_id == Buttons.ResumeButton.custom_id:
            await Buttons.on_resume_btn_press(btn)
        elif btn.custom_id == Buttons.LoopButton.custom_id:
            await Buttons.on_loop_btn_press(btn)
            await VoiceState.update_audio_msg(guild)
        elif btn.custom_id == Buttons.RestartButton.custom_id:
            await Buttons.on_restart_btn_press(btn)
        elif btn.custom_id == Buttons.SkipButton.custom_id:
            await Buttons.on_skip_btn_press(btn)
#----------------------------------------------------------------#
#Now playing

    @commands.guild_only()
    @commands.command(aliases=["np", "nowplaying", "now"],
                      description='🔊 Display the current audio playing in the server',
                      usage="{}np")
    async def now_playing(self, ctx:commands.Context):
        await Logging.log(f"{ctx.author} used now playing command in [{ctx.guild}] ;")

        queue = ctx.guild.song_queue
        audio_message:discord.Message = queue.audio_message
        #No audio playing (not found the now playing message)
        if audio_message is None:
            return await ctx.reply(MessageString.free_to_use_msg)
        elif ctx.voice_client is None:
            return await ctx.reply(MessageString.free_to_use_msg + "| not in a voice channel")

        #if same text channel
        if audio_message.channel == ctx.channel:
            return await audio_message.reply("*🎧 This is the audio playing right now ~* [{}/{}]".format(Convert.length_format(queue.time_position),
                                                                                                         Convert.length_format(queue[0].duration)))
        #Or not
        await ctx.send(f"🎶 Now playing in {VoiceState.get_current_vc(ctx.guild).mention} - **{queue[0].get('title')}**")
#----------------------------------------------------------------#
#Favourites

    @commands.guild_only()
    @commands.command(aliases=["save", "fav"],
                      description='👍🏻 Add the current song playing to your favourites',
                      usage="{}fav")
    async def favourite(self, ctx:commands.Context):
        #No audio playing
        if not VoiceState.is_playing(ctx.guild):
            return await ctx.reply(MessageString.free_to_use_msg)

        Track = ctx.guild.song_queue[0]

        await Logging.log(f"`{ctx.author}` added `[{Track.title}]` to the fav list in [{ctx.guild}] ;")

        #Add to the list
        Favourites.add_track(ctx.author, Track.title, Track.webpage_url)

        #Responding
        await ctx.reply(MessageString.added_fav_msg.format(Track.title))

#Unfavouriting song

    @commands.command(aliases=['unfav'],
                      description='❣🗒 Remove a song from your favourites',
                      usage="{}unfav 3")
    async def unfavourite(self, ctx:commands.Context, index):
        await Logging.log(f"`{ctx.author}` removed `[{index}]` from the fav list in [{ctx.guild}] ;")
        try:
            index = int(re.findall(r'\d+', index)[0]) - 1
            removedTrackTitle = Favourites.get_track_by_index(ctx.author,index)[0]
            Favourites.remove_track(ctx.author,index)
        except (IndexError,ValueError):
            await ctx.reply("✏ Please enter a vaild index")
        except FileNotFoundError:
            await ctx.reply(MessageString.fav_empty_msg)
        else: 
            await ctx.reply(f"`{removedTrackTitle}` has been removed from your favourites")
        
#Display Favourites

    @commands.command(aliases=["favlist", "myfav"],
                      description='❣🗒 Display every song in your favourites',
                      usage="{}myfav")
    async def display_favourites(self, ctx:commands.Context):
      await Logging.log(f"{ctx.author} used display_favourites command in [{ctx.guild}] ;")

      #Grouping the list in string
      try:
          favs_list = Favourites.get_data(ctx.author)
      except FileNotFoundError:
          return await ctx.reply(MessageString.fav_empty_msg)

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