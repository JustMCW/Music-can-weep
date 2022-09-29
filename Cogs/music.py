#Built-ins
import asyncio
import logging
import re
import os
import datetime
import threading
from functools        import reduce

#Third party libaries
import discord
import youtube_dl
from discord.ext      import commands

#My own modules
import Convert
import Favourites

from main             import BOT_INFO
from subtitles        import Subtitles

from Music.song_queue import SongQueue
from Music.song_track import SongTrack
from Music            import voice_state

from discord          import Interaction

#Literals
from Response         import MessageString, Emojis, Embeds

#----------------------------------------------------------------#

#Btn message sent and delete after
TIMEOUT_SECONDS:int = 60 * 2
VOLUME_PERCENTAGE_LIMIT = 200

#----------------------------------------------------------------#


#Search Audio fromm Youtube
def search_from_youtube(query:str, 
                        ResultLengthLimit:int=5,
                        DurationLimit:int=3*3600) -> list:
    """
    Search youtube videos with a given string.
    Returns a list of search result which the item contains the title, duration, channel etc.
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
                        ["sectionListRenderer"]["contents"]
    QueryList = QueryList[len(QueryList)-2]["itemSectionRenderer"]["contents"] 

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
class MusicCommands(commands.Cog):
    def __init__(self,bot):
        logging.info("MUSIC commands is ready")

        self.bot:commands.Bot = bot

        super().__init__()

#CHANGING BOT'S VOICE CHANNEL
    @commands.bot_has_guild_permissions(connect=True, speak=True)
    @commands.command(aliases=["enter", "j"],
                      description='🎧 Connect to your current voice channel or a given voice channel name',
                      usage = "{}join Music channel")
    async def join(self, 
                   ctx:commands.Context,*,
                   voice_channel:commands.converter.VoiceChannelConverter=None):
        
        try: voice_channel = voice_channel or ctx.author.voice.channel
        except AttributeError: raise commands.errors.UserNotInVoiceChannel("Join a voice channel or specify a voice channel to be joined.")

        await voice_state.join_voice_channel(ctx.guild, voice_channel)
        await ctx.reply(MessageString.join_msg.format(voice_channel.mention))
        await voice_state.update_audio_msg(ctx.guild)

        queue : SongQueue = ctx.guild.song_queue
        if queue:
            from discord import Button,ButtonStyle
            message = await ctx.send(
                f"There are {len(queue)} tracks in the queue, resume ?",
                view=discord.ui.View().add_item(discord.ui.Button(label="Yes",style=ButtonStyle.green,custom_id="resume_queue"))
            )

            try:
                await self.bot.wait_for("interaction",
                                        timeout=20,
                                        check=lambda interaction: interaction.data["component_type"] == 2 and "custom_id" in interaction.data.keys() and interaction.message.id == message.id and interaction.author.id == ctx.author.id)
            except asyncio.TimeoutError:
                pass
            else:
                await ctx.invoke(self.bot.get_command('resume'))
            finally:
                await message.delete()

    @commands.guild_only()
    @commands.command(aliases=["leave", "bye", 'dis', "lev",'l'],
                    description='👋 Disconnect from the current voice channel i am in',
                    usage="{}leave")
    async def disconnect(self, ctx:commands.Context):
        voice_client = ctx.voice_client

        #Not in a voice channel
        if not voice_client: raise commands.errors.NotInVoiceChannel

        #Disconnect from voice_client
        await voice_client.disconnect()
        await ctx.reply(MessageString.leave_msg.format(voice_client.channel.mention))
        
#----------------------------------------------------------------#
#INTERRUPTING THE AUDIO

    @commands.guild_only()
    @commands.command(aliases=["wait"],
                      description='⏸ Pause the current audio',
                      usage="{}pause")
    async def pause(self, ctx:commands.Context):
        
        voice_state.pause_audio(ctx.guild)

        await ctx.reply(MessageString.paused_audio_msg)
        

    @commands.guild_only()
    @commands.command(aliases=["continue", "unpause"],
                      description='▶️ Resume the current audio',
                      usage="{}resume")
    async def resume(self, ctx:commands.Context):
        """
        Resume the player.
        
        If player is not found,
        join voice channel (if not already in one) and play the first track in the queue.
        """

        guild:discord.Guild              = ctx.guild
        queue:SongQueue                  = guild.song_queue      
        current_track:SongTrack          = queue.get(0)

        #Try to resume the audio like usual
        try:
            voice_state.resume_audio(guild)
        #Error encountered, player is not found
        except (commands.errors.NotInVoiceChannel,commands.errors.NoAudioPlaying) as resume_error: 
            
            #Stop if there is no track in the queue at all
            if not current_track:
                raise resume_error if isinstance(resume_error,commands.errors.NoAudioPlaying) else commands.errors.NoAudioPlaying

            #Check for voice
            if isinstance(resume_error,commands.errors.NotInVoiceChannel):
                try:
                    await voice_state.join_voice_channel(guild, ctx.author.voice.channel)
                except AttributeError:
                    raise resume_error

            #Play the track
            threading.Thread(
                target=Subtitles.sync_subtitles,
                args=(queue,ctx.channel,current_track)
            ).start()

            queue.play_first(guild.voice_client)

            await voice_state.create_audio_message(current_track, await ctx.send("▶️ Continue to play tracks in the queue"))
        
        #Successfully resumed like usual, send response.
        else:
            await ctx.reply(MessageString.resumed_audio_msg)       

    @commands.guild_only()
    @commands.command(aliases=["fast_forward","fwd"],
                      description = "⏭ Fast-foward the time position of the current audio for a certain amount of time.",
                      usage="{0}fwd 10\n{0}foward 10:30")
    async def forward(self,ctx,*,time:str):
        """
        Fast-foward the player by time given by the user
        """
        voicec:discord.VoiceClient = ctx.voice_client

        if voicec is None or not voicec.is_playing(): 
            raise commands.errors.NoAudioPlaying
        
        guild   :discord.Guild = ctx.guild
        queue   :SongQueue     = guild.song_queue
        fwd_sec :float         = Convert.time_to_sec(time)

        if queue[0].duration < (fwd_sec+queue.time_position):
            await ctx.reply("Ended the current track")
            return voicec.stop()

        voice_state.pause_audio(guild)
        add_loop = round(fwd_sec * 50 / queue.speed)
        queue._raw_fwd(add_loop) #Finshed the audio
        voice_state.resume_audio(guild)

        await ctx.reply(f"*⏭ Fast-fowarded for {Convert.length_format(fwd_sec)}*")

    @commands.guild_only()
    @commands.command(aliases=["jump"],
                      description="⏏️ Move the time position of the current audio, format : [Hours:Minutes:Seconds] or literal seconds like 3600 (an hour). This is a experimental command.",
                      usage="{}seek 2:30")
    async def seek(self,ctx:commands.Context,*,time_position):
        queue = ctx.guild.song_queue
        try:
            position_sec:float = Convert.time_to_sec(time_position)
            if position_sec >= queue[0].duration:
                await ctx.voice_client.stop()
            await voice_state.restart_track(ctx.guild,position=position_sec/queue.speed)
        except AttributeError:
            raise discord.errors.NoAudioPlaying
        except ValueError:
            await ctx.reply(f"Invaild time position, format : {ctx.prefix}{ctx.invoked_with} [Hours:Minutes:Seconds]")
        else:
            await ctx.reply(f"⏏️ Moving audio's time position to `{Convert.length_format(position_sec)}` (It might take a while depend on the length of the audio)")
            queue[0].time_position = position_sec

    @commands.guild_only()
    @commands.command(aliases=["previous"],
                      description="⏪ Return to the last song played",
                      usage="{}previous")
    async def last(self, ctx:commands.Context):
        if ctx.guild.song_queue.history:
            voice_state.rewind_track(ctx.guild)

            await ctx.reply(MessageString.rewind_audio_msg)
        else:
            await ctx.reply("N")
        
    @commands.guild_only()
    @commands.command(aliases=["next"],
                      description='⏩ skip to the next audio in the queue',
                      usage="{}skip")
    async def skip(self, ctx:commands.Context):
        
        voice_state.skip_track(ctx.guild)

        await ctx.reply(MessageString.skipped_audio_msg)    

    @commands.guild_only()
    @commands.command(description='⏹ stop the current audio from playing 🚫',
                      usuge="{}stop")
    async def stop(self, ctx:commands.Context):
        #Checking
        if not ctx.voice_client:
            raise commands.errors.NotInVoiceChannel
        if not ctx.voice_client.is_playing():
            raise commands.errors.NoAudioPlaying
        
        voice_state.skip_track()
        await ctx.voice_client.disconnect()

        await ctx.reply(MessageString.stopped_audio_msg)
        
    @commands.guild_only()
    @commands.command(aliases=["replay", "re"],
                      description='🔄 restart the current audio track',
                      usage="{}replay")
    async def restart(self, ctx:commands.Context):

        await voice_state.restart_track(ctx.guild)

        await ctx.reply(MessageString.restarted_audio_msg)
        
#----------------------------------------------------------------#

    @commands.guild_only()
    @commands.command(aliases=["vol"],
                    description='📶 set audio volume to a percentage (0% - 200%)',
                    usage="{}vol 70")
    async def volume(self, ctx:commands.Context, volume_to_set):

        #Try getting the volume_percentage from the message
        try: volume_percentage = Convert.extract_int_from_str(volume_to_set)
        except ValueError: return await ctx.reply("🎧 Please enter a vaild volume percentage 🔊")
        
        
        #Volume higher than the limit
        if volume_percentage > VOLUME_PERCENTAGE_LIMIT and ctx.author.id != self.bot.owner_id:
            return await ctx.reply(f"🚫 Please enter a volume below {VOLUME_PERCENTAGE_LIMIT}% (to protect yours and other's ears 👍🏻)")

        guild       :discord.Guild       = ctx.guild
        voice_client:discord.VoiceClient = ctx.voice_client
        true_volume :float               = volume_percentage / 100 * BOT_INFO.InitialVolume #Actual volume to be set to
        
        #Updating to the new value
        guild.song_queue.volume = true_volume
        if voice_client and voice_client.source:
            voice_client.source.volume = true_volume

        await ctx.reply(f"🔊 Volume has been set to {round(volume_percentage,3)}%")
        await voice_state.update_audio_msg(guild)

    @commands.guild_only()
    @commands.command(aliasas=[],
                      description="Changes the pitch of the audio playing. ",
                      usage="{}pitch 1.1")
    async def pitch(self,ctx:commands.Context, new_pitch):

        guild = ctx.guild
        queue = guild.song_queue
        try:
            if float(new_pitch) <= 0:
                raise ValueError

            #speed / pitch >= 0.5
            queue.pitch = float(new_pitch)
        except ValueError:
            return await ctx.reply("Invalid pitch.")
        if guild.voice_client and guild.voice_client._player and queue:
            voice_state.pause_audio(guild)
            await voice_state.restart_track(ctx.guild)#,passing=True,position = (queue._player_loops)/50)
            

        await ctx.reply(f"Successful changed the pitch to `{new_pitch}`.")
        await voice_state.update_audio_msg(guild)

    commands.guild_only()
    @commands.command(aliasas=[],
                      description="Changes the speed of the audio playing, can range between `0.5` - `5` ",
                      usage="{}speed 1.1")
    async def speed(self,ctx:commands.Context, new_speed):
        guild = ctx.guild

        try:
            new_speed = float(new_speed)
            if new_speed <= 0:
                voice_state.pause_audio(guild)
                return await ctx.reply(MessageString.paused_audio_msg)
            elif new_speed < 0.5 or new_speed > 5:
                return await ctx.reply("Speed can only range between `0.5-5`.")

            guild.song_queue.speed = new_speed
        except ValueError:
            return await ctx.reply("Invalid speed.")
        if guild.voice_client and guild.voice_client._player and guild.song_queue:
            await voice_state.restart_track(guild)

        await ctx.reply(f"Successful changed the speed to `{new_speed}`.")
        await voice_state.update_audio_msg(guild)


    @commands.guild_only()
    @commands.command(aliases=["looping","repeat"],
                      description='🔂 Enable / Disable single audio track looping\nWhen enabled tracks will restart after playing',
                      usage="{}loop on")
    async def loop(self, ctx:commands.Context, mode=None):
        guild   : discord.Guild = ctx.guild
        new_loop: bool          = commands.core._convert_to_bool(mode) if mode else not guild.song_queue.looping

        guild.song_queue.looping = new_loop

        await ctx.reply(MessageString.loop_audio_msg.format(Convert.bool_to_str(new_loop)))
        await voice_state.update_audio_msg(guild)

        
        
#----------------------------------------------------------------#
#Playing audio

    @commands.bot_has_guild_permissions(connect=True, speak=True)
    @commands.command(aliases=["p","music"],
                     description='🔎 Search and play audio with a given YOUTUBE link or from keywords 🎧',
                     usage="{0}play https://www.youtube.com/watch?v=GrAchTdepsU\n{0}p mood\n{0}play fav 4"
    )
    async def play(self,
                   ctx:commands.Context,
                   *,
                   query:str, #URL / Favourite track index / Keyword
                   btn:Interaction=None #This will be present if this command was invoked from a play_again button
    ):
        """
        0.Check for voice channel

        1.Determines whether the input is URL, favourite track index or keyword
        2.Transform it into a valid url
        3.Extract info from it with Youtube-dl
        4.Join voice channel if not joined
        5.Add to queue
        6.Play it if there is no other tracks in the queue
        7.Send the discord message indicating the audio track playing
        """
        

        guild       : discord.Guild       = ctx.guild
        author      : discord.Member      = getattr(btn,"user",ctx.author)
        voice_client: discord.VoiceClient = ctx.voice_client or author.voice #It can be either our bots vc or the user's vc
        reply_msg   : discord.Message     = None  #This will be the message for the audio message

        #Check for voice channel
        if voice_client is None:
            if btn:
                #Give a button respond instead so it doesn't tell everyone else
                return await btn.response.send_message(content=MessageString.user_not_in_vc_msg,ephemeral=True)
            raise commands.errors.UserNotInVoiceChannel("You need to be in a voice channel.")

        #Triggered by play_again button (so it must be a valid URL because it was played successful before)            
        if btn:
            #Suppress the interaction failed message and response 
            await btn.response.edit_message(content=btn.message.content)
            reply_msg = await ctx.reply(content=f"🎻 {author.mention} requests to play this song again")

        #URL
        elif "https://" in query or "HTTP://" in query:
            #Match the link in the query
            yt_vid_link_matches = re.findall(r"(https|HTTP)://(youtu\.be|www.youtube.com)(/shorts)?/(watch\?v=)?([A-Za-z0-9\-_]{11})",query)
            # yt_pl_link_matches = re.findall(r"(https|HTTP)://(youtu\.be|www.youtube.com)(/shorts)?/(watch\?v=)?([A-Za-z0-9\-_]{11})",query)
            #https://www.youtube.com/playlist?list=PLVl73jKWzwn-20H8azDxpg8Ewop5DlZzT
            
            #Matched
            if yt_vid_link_matches: 
                query = "https://www.youtube.com/watch?v="+yt_vid_link_matches[0][4]
                reply_msg = await ctx.send(f"{Emojis.YOUTUBE_ICON} A Youtube link is selected")

            #Sound cloud link
            elif "soundcloud.com" in query:
                reply_msg = await ctx.send(f"☁️ A Soundcloud link is selected")

            #Invalid
            else:
                return await ctx.send("Oops ! Only Youtube and Soundcloud links are supported ! ")

        #Favourite Index
        elif 'fav' in query.lower():
            #Get the number
            try:
                index = Convert.extract_int_from_str(query)
            except ValueError:
                return await ctx.reply("Invalid favourite index !")
            
            #Get the track url from the number index in the user's favourite.
            try:
                _,link = Favourites.get_track_by_index(author, index-1)
            except IndexError:
                return await ctx.reply(f"Unable to get **#{index}** from your favourite track list.")

            #Good to go
            query = link
            reply_msg = await ctx.send(f"🎧 Track **#{index}** in {author.mention}'s favourites has been selected")
                    
        #Keyword
        else:
            #Get the search result
            try:
                search_result:list = search_from_youtube(query,ResultLengthLimit=5)
            except IndexError:
                return await ctx.reply(f"No search result was found for `{query}` ...")

            #Send the message for asking the user
            option_message:discord.Message = await ctx.send(**Embeds.generate_search_result_attachments(search_result))
            
            #Get which button user pressed, and make sure that it is the user who press the buttons
            try:
                choicesInteraction: discord.Interaction = await self.bot.wait_for("interaction",
                                                            timeout=TIMEOUT_SECONDS,
                                                            check=lambda interaction: interaction.data["component_type"] == 2 and "custom_id" in interaction.data.keys()
                                                            # check=lambda btn: btn.author == author and btn.message.id == option_message.id
                                                            )
            #Not selected
            except asyncio.TimeoutError:
                return await option_message.edit(embed=Embeds.NoTrackSelectedEmbed,
                                            view=None)
            #Received option
            else:
                selected_index = int(choicesInteraction.data["custom_id"])

                await choicesInteraction.response.edit_message(content=f"{Emojis.YOUTUBE_ICON} Song **#{selected_index+1}** in the youtube search result has been selected",view = None)
                reply_msg = await ctx.fetch_message(option_message.id)
                query = f'https://www.youtube.com/watch?v={search_result[selected_index]["videoId"]}'


        #We now have the exact url that lead us to the audio regardless of what the user've typed, let's find and play it.
        
        queue = guild.song_queue
        #Create the track with yt-dl
        try:
            NewTrack:SongTrack = await self.bot.loop.run_in_executor(None,
              lambda: SongTrack.create_track(query=query,
                                             requester=author,
                                             request_message=reply_msg
                                             ))
        #Extraction Failed
        except youtube_dl.utils.YoutubeDLError as yt_dl_error:
            logging.warning(yt_dl_error.__class__.__name__)

            utils = youtube_dl.utils

            for error,error_message in {utils.UnsupportedError:"Sorry, this url is not supported !",
                                        utils.UnavailableVideoError:"Video was unavailable",
                                        utils.DownloadError: str(yt_dl_error).replace("ERROR: ",""),
                                        }.items():
                if isinstance(yt_dl_error,error):
                    return await reply_msg.reply(f"An error was occurred : {error_message}")

            #Raise the error if it was not in the above dictionary
            logging.error(yt_dl_error)
            raise yt_dl_error

        #Extraction Successful
        else:
            logging.info("Succesfully extraced info")
            #Stop current audio (if queuing is disabled)
            if guild.voice_client: 
                if not (await queue.enabled):
                    guild.voice_client.stop()
            else:
                #Join Voice channel
                if author.voice:
                    await voice_state.join_voice_channel(guild,author.voice.channel)
                else: #User left during the loading is taking place
                    await reply_msg.edit(content = "User left the voice channel, the track was cancled.")

            queue.append(NewTrack)
            
            if queue.get(1) is not None:
                await reply_msg.edit(embed=discord.Embed(title = f"\"{NewTrack.title}\" has been added to the queue",
                                                         color=discord.Color.from_rgb(255, 255, 255))
                                              .add_field(name="Length ↔️",
                                                         value=f"`{Convert.length_format(NewTrack.duration)}`")
                                              .add_field(name = "Position in queue 🔢",
                                                         value=len(queue)-1)
                                          .set_thumbnail(url = NewTrack.thumbnail)
                                    )
                if voice_state.is_playing(guild):
                    return

                reply_msg = ctx.channel
                NewTrack = queue[0]

            #Repeat function after the audio

            threading.Thread(
                target=Subtitles.sync_subtitles,
                args=(queue,ctx.channel,NewTrack)
            ).start()
            #Play the audio
            try:
                queue.play_first(guild.voice_client)
            except discord.errors.ClientException as cl_exce:
                if cl_exce.args[0] == 'Already playing audio.':
                    if await queue.enabled:
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
                    raise cl_exce
            else:
                #Make our audio message
                await voice_state.create_audio_message(NewTrack,reply_msg or ctx.channel)
            
#----------------------------------------------------------------#
#QUEUE
    @commands.guild_only()
    @commands.group(description="🔧 You can manage the song queue with this group of command",
                    aliases = ["que","qeueu","q"],
                    usage="{0}queue display\n{0}q clear")
    async def queue(self,ctx:commands.Context):
        
        guild:discord.Guild = ctx.guild

        if not (await guild.song_queue.enabled): raise commands.errors.QueueDisabled("Queuing is disabled in {0}.".format(guild.name))

        if ctx.invoked_subcommand is None:
            def get_params_str(cmd)->str:
                if list(cmd.clean_params):
                    return f"`[{']` `['.join(list(cmd.clean_params))}]`"
                return ""


            await ctx.reply(embed=discord.Embed(title = "Queue commands :",
                                                description = "\n".join([f"{ctx.prefix}queue **{cmd.name}** {get_params_str(cmd)}" for cmd in ctx.command.walk_commands() ]),
                                                color = discord.Color.from_rgb(255,255,255)))

    @commands.guild_only()
    @queue.command(description="📋 Display tracks in the song queue",
                   aliases=["show"],
                   usage="{}queue display")
    async def display(self,ctx):
        """
        Display the song queue as a discord embed
        """
        queue:SongQueue = ctx.guild.song_queue

        if not queue: 
            raise commands.errors.QueueEmpty("No tracks in the queue for display.")
        
        symbol = "▶︎" if not voice_state.is_paused(ctx.guild) else "\\⏸"
        await ctx.send(embed = discord.Embed(title = f"🎧 Queue | Track Count : {len(queue)} | Full Length : {Convert.length_format(queue.total_length)} | Repeat queue : {Convert.bool_to_str(queue.queue_looping)}",
                                            #                           **   [Index] if is 1st track [Playing Sign]**    title   (newline)             `Length`               |         @Requester         Do this for every track in the queue
                                            description = "\n".join([f"**{f'[ {i} ]' if i > 0 else f'[{symbol}]'}** {track.title}\n> `{Convert.length_format(track.duration)}` | {track.requester.mention}" for i,track in enumerate(list(queue))]),
                                            color=discord.Color.from_rgb(255, 255, 255),
                                            timestamp=datetime.datetime.now()))

    @commands.guild_only()
    @queue.group(description=" Remove one song track by position in the queue, or remove all song tracks that apply to the statement ",
                    aliases=["rm","delete","del"],
                    usage="{0}queue remove 1\n{0}q rm dup")
    async def remove(self,ctx:commands.Context):
        
        guild:discord.Guild = ctx.guild
        queue:SongQueue     = guild.song_queue

        if not queue:
            raise commands.errors.QueueEmpty("There must be songs in the queue to be removed.")

        if ctx.invoked_subcommand is None:     
            #Removing by position
            
            position:str = ctx.subcommand_passed

            if not position:
                raise commands.errors.MissingRequiredArgument("position")

            try:
                position:int = Convert.extract_int_from_str(position)

            except ValueError:

                return await ctx.reply(f"Please enter a valid number for position.")
            
            else:
                poped_track = queue.get(position)
                
                del queue[position]

                if position == 0 and ctx.voice_client and ctx.voice_client.source:
                    voice_state.restart_track(guild)
                
            
                await ctx.reply(f"**#{position}** - `{poped_track.title}` has been removed from the queue")
        
    
    @commands.guild_only()
    @remove.command(description="Remove tracks which are duplicated in the queue",
                    aliases=["dup","repeated"],
                    usage="{}queue remove duplicate")
    async def duplicated(self,ctx):

        queue   :SongQueue       = ctx.guild.song_queue
        not_rep :list[SongTrack] = []

        def is_dup(appeared:list,item:SongTrack):
            if item.webpage_url not in appeared:
                appeared.append(item.webpage_url)
                not_rep.append(item)
            return appeared
        
        reduce(is_dup,queue,[])
        removed_index:int = len(queue) - len(not_rep)

        if removed_index == 0: return await ctx.reply("None of the track is repeated, therefore no track was removed")

        queue.clear()
        queue.extend(not_rep)

        await ctx.reply(f"Successfully removed `{removed_index}` duplicated tracks from the queue.")
    
    @commands.guild_only()
    @remove.command(description="Remove tracks which their requester is not in the bot's voice channel",
                    aliases=["left_vc","left"],
                    usage="{}queue remove left")
    async def left_user(self,ctx:commands.Context):

        guild          : discord.Guild        = ctx.guild
        queue          : SongQueue            = guild.song_queue
        user_in_vc     : list[discord.Member] = voice_state.get_non_bot_vc_members()
        user_in_vc_ids : list[int]            = map(lambda mem:mem.id, user_in_vc)
        track_in_vc    : list[SongQueue]      = filter(lambda t: t.requester.id in user_in_vc_ids, queue)
        remove_count   : int                  = len(queue) - len(track_in_vc)

        if remove_count == 0: return await ctx.reply("No requester lefted the voice channel, therefore no track was removed.")

        queue.clear()
        queue.extend(track_in_vc)
        await ctx.reply(f"Successfully removed `{remove_count}` tracks from the queue.")

    @commands.guild_only()
    @queue.command(description="🧹 Removes every track in the queue",
                   aliases=["empty","clr"],
                   usage="{}queue clear")
    async def clear(self,ctx):
        from Music.song_queue import AudioControlState
        queue:SongQueue = ctx.guild.song_queue

        queue.audio_control_status = AudioControlState.CLEAR
        queue.clear()

        await voice_state.clear_audio_message(ctx.guild)

        if ctx.voice_client: ctx.voice_client.stop()

        await ctx.reply("🗒 The queue has been cleared")

    @commands.guild_only()
    @queue.command(description="🔁 Swap the position of two tracks in the queue",
                   usage="{}queue swap 1 2")
    async def swap(self,ctx,position_1,position_2):
        queue:SongQueue = ctx.guild.song_queue

        try: queue.swap(position_1,position_2)
        except (TypeError,IndexError): return await ctx.reply("❌ Invaild position")

        await ctx.reply(f"Swapped **#{position_1}** with **#{position_2}** in the queue")

    @commands.guild_only()
    @queue.command(description="🔃 Reverse the position of the whole queue",
                    usage="{}queue reverse")
    async def reverse(self,ctx):
        queue   :SongQueue = ctx.guild.song_queue
        playing :SongTrack = queue.popleft() #We exclude the track playing

        queue.reverse()
        queue.appendleft(playing) #Add the playing track back

        await ctx.reply("🔃 The queue has been *reversed*")

    @commands.guild_only()
    @queue.command(description="🎲 Randomize the position of every track in the queue",
                   aliases = ["random","randomize","sfl"],
                   usage="{}queue shuffle")
    async def shuffle(self,ctx):
        queue:SongQueue = ctx.guild.song_queue

        queue.shuffle()

        await ctx.reply("🎲 The queue has been *shuffled*")

    @commands.guild_only()
    @queue.command(description='🔂 Enable / Disable queue looping.\nWhen enabled, tracks will be moved to the last at the queue after finsh playing',
                   aliases=["loop","looping","repeat_queue",'setloop','setlooping',"toggleloop","toggle_looping",'changelooping','lop'],
                   usage="{}queue repeat on")
    async def repeat(self,
                    ctx:commands.Context,
                    select_mode:str=None):
        guild     :discord.Guild = ctx.guild
        queue     :SongQueue     = guild.song_queue
        new_qloop :bool          = commands.core._convert_to_bool(select_mode) if select_mode else not queue.queue_looping

        queue.queue_looping = new_qloop
        await ctx.reply(MessageString.queue_loop_audio_msg.format(Convert.bool_to_str(new_qloop)))
        await voice_state.update_audio_msg(guild)



#----------------------------------------------------------------#

    @commands.is_owner()
    @queue.command(description='Ouput the queue as a txt file, can be imported again through the import command')
    async def export(self,ctx:commands.Context):
        filename:str       = f"q{ctx.guild.id}.txt"
        queue   :SongQueue = ctx.guild.song_queue

        if not queue: raise commands.errors.QueueEmpty("No tracks to export.")

        #Create a file the contains the queue in a txt
        with open(filename,"x") as qfile:
            qfile.write("\n".join([track.webpage_url for track in queue]))

        await ctx.send(file=discord.File(filename))
        os.remove(filename)

    @commands.is_owner()
    @queue.command(description='Input songs through a txt file, you can also export the current queue with queue export',
                   aliases=["import"],
                   usage="{}queue import [place your txt file in the attachments]")
    async def from_file(self,ctx:commands.Context):
        queue       :SongQueue          = ctx.guild.song_queue
        attachments :discord.Attachment = ctx.message.attachments[0]

        if not attachments: return await ctx.reply("Please upload a txt file")

        if "utf-8" not in (attachments.content_type): return await ctx.reply("Invaild file type. (must be txt and utf-8 encoded)")   

        mes :discord.Message = await ctx.reply("This might take a while ...")
        data:list[str]       = (await attachments.read()).decode("utf-8").split("\n")

        for line in data:
            if not line: continue

            try:
                queue.append(await self.bot.loop.run_in_executor(None,
                                                                lambda: SongTrack.create_track(query=line,
                                                                                                requester=ctx.author,
                                                                                                request_message= mes)))
            except youtube_dl.utils.YoutubeDLError as yt_dl_error:
                await ctx.send(f"Failed to add {line} to the queue because `{yt_dl_error}`")

        await mes.edit(f"Successfully added {len(data)-1} tracks to the queue !")
                                
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
                if not voice_state.get_non_bot_vc_members(guild):
                    logging.info("Nobody is in vc with me")

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
                    try:
                        if voice_client and not voice_state.get_non_bot_vc_members(guild):
                            await voice_client.disconnect()
                    except commands.errors.NotInVoiceChannel:
                        pass
        #---------------------#
        #Bot moved channel
        elif member == self.bot.user:
            if before.channel and after.channel:
                if before.channel.id != after.channel.id: #Moving channel
                    if voice_client:
                        logging.info("Pasued because moved")
                        guild.voice_client.pause()

#Button detecting
    @commands.Cog.listener()
    async def on_interaction(self, interaction:Interaction):

        if not (interaction.data["component_type"] == 2 and "custom_id" in interaction.data.keys()):
            return print("Oof")

        btn = interaction
        custom_id = btn.data["custom_id"]

        from Buttons import Buttons
        guild = btn.guild

        if logging.root.isEnabledFor(logging.getLevelName("COMMAND_INFO")):
            asyncio.create_task(logging.webhook_log(embed= discord.Embed(title = f"{btn.guild.name+' | ' if btn.guild else ''}{btn.channel}",
                                                                        description = f"**Pressed the {custom_id} button**",
                                                                        color=discord.Color.from_rgb(255,255,255),
                                                                        timestamp = datetime.datetime.now()
                                                                        ).set_author(
                                                                        name =btn.author,
                                                                        icon_url= btn.author.display_avatar),
                                                    username="Button Logger"))
        
        if interaction.response.is_done() or guild is None:  return
        
        queue = guild.song_queue

        #Tons of Buttons
        if custom_id == Buttons.FavouriteButton.custom_id:
            await Buttons.on_favourite_btn_press(btn)

        elif custom_id == Buttons.PlayAgainButton.custom_id:
            await Buttons.on_play_again_btn_press(btn,self.bot)

        #Clearing glitched messages
        elif queue.get(0) is None or queue.audio_message is None or queue.audio_message.id != interaction.message.id or not voice_state.is_playing(guild):
            if not custom_id.isnumeric() and btn.message.embeds:
                new_embed:discord.Embed = interaction.message.embeds[0]
                await btn.response.edit_message(content=btn.message.content)
                if len(new_embed.fields) == 9:
                    await voice_state.clear_audio_message(specific_message=interaction.message)

        elif custom_id == Buttons.SubtitlesButton.custom_id:
            await Buttons.on_subtitles_btn_press(btn,self.bot)
        elif custom_id == Buttons.PlayPauseButton.custom_id:
            await Buttons.on_playpause_btn_press(btn)
        elif custom_id == Buttons.RewindButton.custom_id:
            await Buttons.on_rewind_btn_press(btn)
        elif custom_id == Buttons.LoopButton.custom_id:
            await Buttons.on_loop_btn_press(btn)
            await voice_state.update_audio_msg(guild)
        elif custom_id == Buttons.RestartButton.custom_id:
            await Buttons.on_restart_btn_press(btn)
        elif custom_id == Buttons.SkipButton.custom_id:
            await Buttons.on_skip_btn_press(btn)

#----------------------------------------------------------------#
#Now playing

    @commands.guild_only()
    @commands.command(aliases=["np", "nowplaying", "now"],
                      description='🔊 Display the current audio playing in the server',
                      usage="{}np")
    async def now_playing(self, ctx:commands.Context):
        

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
        await ctx.send(f"🎶 Now playing in {voice_state.get_current_vc(ctx.guild).mention} - **{queue[0].title}**")

    @commands.guild_only()
    @commands.command(description="Send the current audio as a file which is available for downloading.")
    async def download(self,ctx:commands.Context):
        queue = ctx.guild.song_queue
        try:
            playing_track : SongTrack = queue[0]
        except IndexError:
            raise discord.errors.NoAudioPlaying

        src_url:str = playing_track.src_url
        file_name:str = playing_track.title.replace("/","|") + ".mp3"
        
        import subprocess

        proc_mes = await ctx.reply("Processing ...")
        subprocess.Popen(args=["./ffmpeg",
                    "-i",f"{src_url}",
                    '-loglevel','warning',
                    # '-ac', '2',
                    f"./{file_name}"
                    ],creationflags=0)
        cd = 3
        last_progress = 0
        combo = 0

        for _ in range(300):
            
            try:
                progress = os.path.getsize(f'./{file_name}')/playing_track.filesize

                if progress == last_progress:
                    combo += 1
                else:
                    last_progress = progress
                    combo = 0

                if combo > 2:
                    await proc_mes.edit(content="Successful !")
                    await proc_mes.reply(file=discord.File(f"./{file_name}"))
                    os.remove(f"./{file_name}")
                    return
                else:
                    await proc_mes.edit(proc_mes.content + f" [{round(progress * 100,1)}%]")
                    await asyncio.sleep(cd)
            except FileNotFoundError:
                await asyncio.sleep(cd)
        
       

#----------------------------------------------------------------#
#Favourites (disabled)

#     @commands.guild_only()
#     @commands.command(aliases=["save", "fav"],
#                       description='👍🏻 Add the current song playing to your favourites',
#                       usage="{}fav")
#     async def favourite(self, ctx:commands.Context):
#         ctx.channel
#         #No audio playing
#         if not voice_state.is_playing(ctx.guild):
#             return await ctx.reply(MessageString.free_to_use_msg)

#         Track = ctx.guild.song_queue[0]

#         #Add to the list
#         position:int = Favourites.add_track(ctx.author, Track.title, Track.webpage_url)

#         #Responding
#         await ctx.reply(MessageString.added_fav_msg.format(Track.title,position))

# #Unfavouriting song

#     @commands.command(aliases=['unfav'],
#                       description='❣🗒 Remove a song from your favourites',
#                       usage="{}unfav 3")
#     async def unfavourite(self, ctx:commands.Context,*,index):
        
#         try:
#             index = Convert.extract_int_from_str(index) - 1
#             removedTrackTitle = Favourites.get_track_by_index(ctx.author,index)[0]
#             Favourites.remove_track(ctx.author,index)
#         except ValueError:
#             await ctx.reply("✏ Please enter a vaild index")
#         except FileNotFoundError:
#             await ctx.reply(MessageString.fav_empty_msg)
#         else: 
#             await ctx.reply(f"`{removedTrackTitle}` has been removed from your favourites")
        
# #Display Favourites

#     @commands.command(aliases=["favlist", "myfav"],
#                       description='❣🗒 Display every song in your favourites',
#                       usage="{}myfav")
#     async def display_favourites(self, ctx:commands.Context):
      

#       #Grouping the list in string
#       try:
#           favs_list = Favourites.get_data(ctx.author)
#       except FileNotFoundError:
#           return await ctx.reply(MessageString.fav_empty_msg)

#       wholeList = ""
#       for index, title in enumerate(favs_list):
#           wholeList += "***{}.*** {}\n".format(index + 1,title)

#       #embed =>
#       favouritesEmbed = discord.Embed(title=f"🤍 🎧 Favourites of {ctx.author.name} 🎵",
#                                       description=wholeList,
#                                       color=discord.Color.from_rgb(255, 255, 255),
#                                       timestamp=datetime.datetime.now()
#                         ).set_footer(text="Your favourites would be the available in every server")

#       #sending the embed
#       await ctx.reply(embed=favouritesEmbed)

#----------------------------------------------------------------#
async def setup(BOT):
    await BOT.add_cog(MusicCommands(BOT))