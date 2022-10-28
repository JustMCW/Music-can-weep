#Built-ins
import asyncio
import logging

import re
import os
import datetime
from typing           import List
from functools        import reduce

#Third party libaries
import discord
import youtube_dl
from discord          import Interaction,ButtonStyle
from discord.ext      import commands
from discord.ui       import View,Select,Button


#My own modules
import convert
import favourites

from subtitles        import Subtitles

from Music.song_queue import SongQueue,SongTrack,VOLUME_PERCENTAGE_LIMIT
from Music            import voice_state
from my_buttons       import MusicButtons,UtilityButtons
from youtube_utils    import search_from_youtube,YoutubeVideo

#Literals
from string_literals         import MessageString, MyEmojis

#----------------------------------------------------------------#
TIMEOUT_SECONDS         = 60 * 2

#----------------------------------------------------------------#
#random functions that i don't know where to place


#Take the search result from the function above and make them into buttons and embed
def generate_search_result_attachments(search_result : List[YoutubeVideo]) -> dict:
    """
    Returns the embed + buttons for a youtube search result returned by the `search_from_youtube` function
    """
    #Add the buttons and texts for user to pick
    choices_string:str  = ""


    class _components(View):...
    components = _components()

    for i,video in enumerate(search_result):
        
        title = video.title
        length = video.length

        choices_string += f'{i+1}: {title} `[{length}]`\n'
        components.add_item(Button(label=f"{i+1}",custom_id=f"{i}",style=discord.ButtonStyle.blurple,row=0))
    
    return {
        "embed":discord.Embed(title="🎵  Select a song you would like to play : ( click the buttons below )",
                                description=choices_string,
                                color=discord.Color.from_rgb(255, 255, 255)),
        "view": components
    }
#----------------------------------------------------------------#

#COMMANDS
class MusicCommands(commands.Cog):
    def __init__(self,bot):
        logging.info("MUSIC commands is ready")

        self.bot:commands.Bot = bot

        super().__init__()

    #----------------------------------------------------------------#
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
        initial_vc = ctx.guild.voice_client

        await voice_state.join_voice_channel(ctx.guild, voice_channel)
        await ctx.replywm(MessageString.join_msg.format(voice_channel.mention))
        queue : SongQueue = ctx.guild.song_queue
        await queue.update_audio_message()

        #Ask the user to resume the queue, if there is.
        if queue:
            message = await ctx.send(
                f"There are {len(queue)} tracks in the queue, resume ?",
                view=View().add_item(Button(label="Yes",style=ButtonStyle.green,custom_id="resume_queue"))
            )

            try:
                await self.bot.wait_for("interaction",
                                        timeout=20,
                                        check=lambda interaction: interaction.data["component_type"] == 2 and "custom_id" in interaction.data.keys() and interaction.message.id == message.id and interaction.user.id == ctx.author.id)
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
        await ctx.replywm(MessageString.leave_msg.format(voice_client.channel.mention))
        
    #----------------------------------------------------------------#
    #INTERRUPTING THE AUDIO

    @commands.guild_only()
    @commands.command(aliases=["wait"],
                      description='⏸ Pause the current audio',
                      usage="{}pause")
    async def pause(self, ctx:commands.Context):
        
        voice_state.pause_audio(ctx.guild)

        await ctx.replywm(MessageString.paused_audio_msg)
        
    @commands.guild_only()
    @commands.command(aliases=["continue", "unpause"],
                      description='▶️ Resume the current audio',
                      usage="{}resume")
    async def resume(self, ctx:commands.Context):
        """
        Note : This is not exactly the opposite of pausing.

        Resume the player.
        
        If player is not found,
        join voice channel (if not already in one) and play the first track in the queue.
        """

        guild:discord.Guild              = ctx.guild
        queue:SongQueue                  = guild.song_queue      
        current_track:SongTrack          = queue.current_track

        #Try to resume the audio like usual
        try:
            voice_state.resume_audio(guild)
        #Error encountered, player is not found
        except (commands.errors.NotInVoiceChannel,commands.errors.NoAudioPlaying) as resume_error: 
            
            #Stop if there is no track in the queue at all
            if not current_track:
                raise commands.errors.NoAudioPlaying

            #Check for voice
            if isinstance(resume_error,commands.errors.NotInVoiceChannel):
                try:
                    await voice_state.join_voice_channel(guild, ctx.author.voice.channel)
                except AttributeError:
                    raise resume_error

            #Play the track
            await voice_state.create_audio_message(current_track, await ctx.send("▶️ Continue to play tracks in the queue"))

            queue.play_first()
        
        #Successfully resumed like usual, send response.
        else:
            await ctx.replywm(MessageString.resumed_audio_msg)       

    #----------------------------------------------------------------#
    #SEEKING THROUGHT THE AUDIO
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
        fwd_sec :float         = convert.timestr_to_sec(time)

        if queue[0].duration < (fwd_sec + queue.time_position):
            await ctx.replywm("Ended the current track")
            return voicec.stop()

        voicec.pause()
        queue.time_position += fwd_sec
        voicec.resume()

        await ctx.replywm(f"*⏭ Fast-fowarded for * `{convert.length_format(fwd_sec)}`")

    @commands.guild_only()
    @commands.command(aliases=["rwd"],
                      description = "⏭ Fast-foward the time position of the current audio for a certain amount of time.",
                      usage="{0}fwd 10\n{0}foward 10:30")
    async def rewind(self,ctx,*,time:str):
        """
        Rewind the player by time given by the user
        """
        voicec:discord.VoiceClient = ctx.voice_client

        if voicec is None or not voicec.is_playing(): 
            raise commands.errors.NoAudioPlaying
        
        guild   :discord.Guild = ctx.guild
        queue   :SongQueue     = guild.song_queue
        rwd_sec :float         = convert.timestr_to_sec(time)

        queue[0].time_position -= rwd_sec / queue.tempo

        await ctx.replywm(f"*⏮ Rewinded for * `{convert.length_format(rwd_sec)}`")

    @commands.guild_only()
    @commands.command(aliases=["jump"],
                      description="⏏️ Move the time position of the current audio, format : [Hours:Minutes:Seconds] or literal seconds like 3600 (an hour). This is a experimental command.",
                      usage="{}seek 2:30")
    async def seek(self,ctx:commands.Context,*,time_position):
        queue = ctx.guild.song_queue
        try:
            position_sec:float = convert.timestr_to_sec(time_position)
            if position_sec >= queue[0].duration:
                ctx.voice_client.stop()
            # await voice_state.restart_track(ctx.guild,position=position_sec/queue.tempo)
        except AttributeError:
            raise discord.errors.NoAudioPlaying
        except ValueError:
            await ctx.replywm(f"Invaild time position, format : {ctx.prefix}{ctx.invoked_with} [Hours:Minutes:Seconds]")
        else:
            voice_state.pause_audio(ctx.guild)
            queue.time_position = position_sec
            voice_state.resume_audio(ctx.guild)
            await ctx.replywm(f"*⏏️ Moved the time position to * `{convert.length_format(position_sec)}`")


    @commands.guild_only()
    @commands.command(aliases=["replay", "re"],
                      description='🔄 restart the current audio track, equivalent to seeking to 0',
                      usage="{}replay")
    async def restart(self, ctx:commands.Context):
        ctx.guild.song_queue.time_position = 0
        await ctx.replywm(MessageString.restarted_audio_msg)

    #----------------------------------------------------------------#
    #SEEKING THOUGHT THE SONG QUEUE
    @commands.guild_only()
    @commands.command(aliases=["last","prev"],
                      description="⏪ Return to the previous song played",
                      usage="{}prev 1")
    async def previous(self, ctx:commands.Context,count = 1):
        try: count = int(count)
        except ValueError: count = 1
        voice_state.rewind_track(ctx.guild,count)
        await ctx.send("Rewinded.")
       
            
    @commands.guild_only()
    @commands.command(aliases=['next',"nxt"],
                      description='⏩ skip to the next track in the queue',
                      usage="{}skip 1")
    async def skip(self, ctx:commands.Context,count = 1):
        try: count = int(count)
        except ValueError: count = 1

        voice_state.skip_track(ctx.guild,count)
        await ctx.replywm(MessageString.skipped_audio_msg)    

    @commands.guild_only()
    @commands.command(aliases=["rotate","shf"],
                      description='⏩ skip to the next track and move it to the back of the queue, you can enter negative number to make it shift backward (move last track to the fist)')
    async def shift(self,ctx:commands.Context,count = 1): 
        try: count = int(count)
        except ValueError: count = 1

        voice_state.shift_track(ctx.guild,count)
        await ctx.replywm("Shifted.")   

    @commands.guild_only()
    @commands.command(description='⏹ stop the current audio from playing 🚫',
                      usuge="{}stop")
    async def stop(self, ctx:commands.Context):
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        ctx.guild.song_queue.clear()
        return await ctx.send("Stopped.")
      
    #----------------------------------------------------------------#
    #CONFIGURATION OF THE AUDIO
    @commands.guild_only()
    @commands.command(aliases=["vol"],
                    description='📶 set audio volume to a percentage (0% - 200%)',
                    usage="{}vol 70")
    async def volume(self, ctx:commands.Context, volume_to_set):

        #Try getting the volume_percentage from the message
        try:
             volume_percentage = convert.extract_int_from_str(volume_to_set)
        except ValueError: 
            return await ctx.replywm("🎧 Please enter a vaild volume percentage 🔊")
        
        
        #Volume higher than the limit
        if volume_percentage > VOLUME_PERCENTAGE_LIMIT and ctx.author.id != self.bot.owner_id:
            return await ctx.replywm(f"🚫 Please enter a volume below {VOLUME_PERCENTAGE_LIMIT}% (to protect yours and other's ears 👍🏻)")

        guild       :discord.Guild       = ctx.guild
        guild.song_queue.volume_percentage = volume_percentage
        
        if not guild.song_queue.audio_message:
            await ctx.replywm(f"🔊 Volume has been set to {round(volume_percentage,3)}%")
        await guild.song_queue.update_audio_message()

    @commands.guild_only()
    @commands.command(aliasas=[],
                      description="Changes the pitch of the audio playing. ",
                      usage="{}pitch 1.1")
    async def pitch(self, ctx:commands.Context, new_pitch):

        guild = ctx.guild
        queue = guild.song_queue
        try:
            if float(new_pitch) <= 0:
                raise ValueError

            #speed / pitch >= 0.5
            queue.pitch = float(new_pitch)
        except ValueError:
            return await ctx.replywm("Invalid pitch.")
        if guild.voice_client and guild.voice_client._player and queue:
            voice_state.pause_audio(guild)
            voice_state.replay_track(ctx.guild)#,passing=True,position = (queue._player_loops)/50)
            
        if not guild.song_queue.audio_message:
            await ctx.replywm(f"Successful changed the pitch to `{new_pitch}`.")
        await queue.update_audio_message()

    commands.guild_only()
    @commands.command(aliasas=[],
                      description="Changes the tempo of the audio playing, can range between `0.5` - `5` ",
                      usage="{}tempo 1.1")
    async def tempo(self,ctx:commands.Context, new_tempo):
        guild = ctx.guild

        try:
            new_tempo = float(new_tempo)
            if new_tempo <= 0:
                voice_state.pause_audio(guild)
                return await ctx.replywm(MessageString.paused_audio_msg)
            elif new_tempo < 0.5 or new_tempo > 5:
                return await ctx.replywm("Tempo can only range between `0.5-5`.")

            guild.song_queue.tempo = new_tempo
        except ValueError:
            return await ctx.replywm("Invalid tempo.")
        if guild.voice_client and guild.voice_client._player and guild.song_queue:
            voice_state.replay_track(guild)

        if not guild.song_queue.audio_message:
            await ctx.replywm(f"Successful changed the tempo to `{new_tempo}`.")
        await guild.song_queue.update_audio_message()


    @commands.guild_only()
    @commands.command(aliases=["looping","repeat"],
                      description='🔂 Enable / Disable single audio track looping\nWhen enabled tracks will restart after playing',
                      usage="{}loop on")
    async def loop(self, ctx:commands.Context, mode=None):
        guild   : discord.Guild = ctx.guild
        new_loop: bool          = commands.converter._convert_to_bool(mode) if mode else not guild.song_guild.song_queue.looping

        guild.song_queue.looping = new_loop
        if not guild.song_queue.audio_message:
            await ctx.replywm(MessageString.loop_audio_msg.format(convert.bool_to_str(new_loop)))
        await guild.song_queue.update_audio_message()

    #----------------------------------------------------------------#
    #ACTUALLY PLAYING THE AUDIO

    @commands.bot_has_guild_permissions(connect=True, speak=True)
    @commands.command(aliases=["p","music"],
                     description='🔎 Search and play audio with a given YOUTUBE link or from keywords 🎧',
                     usage="{0}play https://www.youtube.com/watch?v=GrAchTdepsU\n{0}p mood\n{0}play fav 4"
    )
    async def play(self,
                   ctx:commands.Context,
                   *,
                   query:str, #URL / Favourite track index / Keyword
                   _btn:Interaction=None #This will be present if this command was invoked from a play_again button
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
        author      : discord.Member      = getattr(_btn,"user",ctx.author)
        voice_client: discord.VoiceClient = ctx.voice_client or author.voice #It can be either our bots vc or the user's vc
        reply_msg   : discord.Message     = None  #This will be the message for the audio message

        #Check for voice channel
        if voice_client is None:
            if _btn:
                #Give a button respond instead so it doesn't tell everyone else
                return await _btn.response.send_message(content=MessageString.user_not_in_vc_msg,ephemeral=True)
            raise commands.errors.UserNotInVoiceChannel("You need to be in a voice channel.")

        #Triggered by play_again button (so it must be a valid URL because it was played successfully before)            
        if _btn:
            #Suppress the interaction failed message and response 
            await _btn.response.edit_message(content=_btn.message.content)
            reply_msg = await ctx.replywm(content=f"🎻 {author.display_name} requests to play this song again")

        #URL
        elif "https://" in query or "HTTP://" in query:
            #Match the link in the query
            yt_vid_link_matches = re.findall(r"(https|HTTP)://(youtu\.be|www.youtube.com)(/shorts)?/(watch\?v=)?([A-Za-z0-9\-_]{11})",query)
            # yt_pl_link_matches = re.findall(r"(https|HTTP)://(youtu\.be|www.youtube.com)(/shorts)?/(watch\?v=)?([A-Za-z0-9\-_]{11})",query)
            #https://www.youtube.com/playlist?list=PLVl73jKWzwn-20H8azDxpg8Ewop5DlZzT
            
            #Matched
            if yt_vid_link_matches: 
                query = "https://www.youtube.com/watch?v="+yt_vid_link_matches[0][4]
                reply_msg = await ctx.send(f"{MyEmojis.YOUTUBE_ICON} A Youtube link is selected")

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
                index = convert.extract_int_from_str(query)
            except ValueError:
                return await ctx.replywm("Invalid favourite index !")
            
            #Get the track url from the number index in the user's favourite.
            try:
                _,link = favourites.get_track_by_index(author, index-1)
            except IndexError:
                return await ctx.replywm(f"Unable to get **#{index}** from your favourite track list.")

            #Good to go
            query = link
            reply_msg = await ctx.send(f"🎧 Track **#{index}** in {author.display_name}'s favourites has been selected")
                    
        #Keyword
        else:
            #Get the search result
            try:
                search_result:list = search_from_youtube(query,ResultLengthLimit=5)
            except IndexError:
                return await ctx.replywm(f"No search result was found for `{query}` ...")

            #Send the message for asking the user
            option_message : discord.Message = await ctx.send(**generate_search_result_attachments(search_result))
            
            #Get which button user pressed, and make sure that it is the user who press the buttons
            try:
                choice_interaction: discord.Interaction = await self.bot.wait_for("interaction",
                                                            timeout=TIMEOUT_SECONDS,
                                                            check=lambda interaction: interaction.data["component_type"] == 2 and "custom_id" in interaction.data.keys() and interaction.message.id == option_message.id
                                                            # check=lambda btn: btn.author == author and btn.message.id == option_message.id
                                                            )
            #Not selected
            except asyncio.TimeoutError:
                return await option_message.edit(embed=discord.Embed(title=f"{MyEmojis.cute_panda} No track was selected !",
                                                                    description=f"You thought for too long ( {2} minutes ), use the command again !",
                                                                    color=discord.Color.from_rgb(255, 255, 255)),
                                            view=None)
            #Received option
            else:
                selected_index = int(choice_interaction.data["custom_id"])

                await choice_interaction.response.edit_message(content=f"{MyEmojis.YOUTUBE_ICON} Song **#{selected_index+1}** in the youtube search result has been selected",view = None)
                reply_msg = await ctx.fetch_message(option_message.id)
                query = f'https://www.youtube.com/watch?v={search_result[selected_index].videoId}'



    ### We now have the exact url that lead us to the audio regardless of what the user've typed, let's extract the info and play it.
        

        queue : SongQueue = guild.song_queue
        #Create the track
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
                    return await reply_msg.replywm(f"An error occurred : {error_message}")

            #Raise the error if it was not in the above dictionary
            logging.error(yt_dl_error)
            raise yt_dl_error

        #Extraction Successful
        else:
            #Stop current audio (if queuing is disabled)
            if guild.voice_client: 
                if not queue.enabled:
                    guild.voice_client.stop()
                    while queue.current_track:
                        await asyncio.sleep(1)
            else: #Join Voice channel
                if author.voice:
                    await voice_state.join_voice_channel(guild,author.voice.channel)
                else: #User left during the loading was taking place
                    await reply_msg.edit(content = "User left the voice channel, the track was cancled.")

            
            if queue.get(0) and queue.enabled:
                await reply_msg.edit(embed=discord.Embed(title = f"\"{NewTrack.title}\" has been added to the queue",
                                                         color=discord.Color.from_rgb(255, 255, 255))
                                              .add_field(name="Length ↔️",
                                                         value=f"`{convert.length_format(NewTrack.duration)}`")
                                              .add_field(name = "Position in queue 🔢",
                                                         value=len(queue))
                                          .set_thumbnail(url = NewTrack.thumbnail)
                                    )
                if voice_state.is_playing(guild):
                    
                    queue.append(NewTrack)
                    if len(queue) == 2:
                        await queue.update_audio_message()
                    return

                reply_msg = ctx.channel
                NewTrack = queue[0]

            queue.append(NewTrack)
            # #Make our audio message
            await voice_state.create_audio_message(NewTrack,reply_msg or ctx.channel)

            #Play the audio, we are not actually playing the audio we just extracted, but the first track in queue
            try:
                queue.play_first()
            except discord.errors.ClientException as cl_exce:
                if cl_exce.args[0] == 'Already playing audio.':
                    if queue.enabled:
                        return await reply_msg.edit(embed=discord.Embed(title = f"\"{NewTrack.title}\" has been added to the queue",
                                                color=discord.Color.from_rgb(255, 255, 255))
                                    .add_field(name="Length ↔️",
                                                value=f"`{convert.length_format(NewTrack.duration)}`")
                                    .add_field(name = "Position in queue 🔢",
                                                value=len(queue)-1)
                                .set_thumbnail(url = NewTrack.thumbnail))
                        
                    return await ctx.replywm("Unable to play this track because another tracks was requested at the same time")
                raise cl_exce

           
            
    #----------------------------------------------------------------#
    #QUEUE
    @commands.guild_only()
    @commands.group(description="🔧 You can manage the song queue with this group of command",
                    aliases = ["que","qeueu","q"],
                    usage="{0}queue display\n{0}q clear")
    async def queue(self,ctx:commands.Context):
        
        guild:discord.Guild = ctx.guild

        if not guild.song_queue.enabled: raise commands.errors.QueueDisabled("Queuing is disabled in {0}.".format(guild.name))

        if ctx.invoked_subcommand is None:
            def get_params_str(cmd)->str:
                if list(cmd.clean_params):
                    return f"`[{']` `['.join(list(cmd.clean_params))}]`"
                return ""


            await ctx.replywm(embed=discord.Embed(title = "Queue commands :",
                                                description = "\n".join([f"{ctx.prefix}queue **{cmd.name}** {get_params_str(cmd)}" for cmd in ctx.command.walk_commands() ]),
                                                color = discord.Color.from_rgb(255,255,255)))

    @commands.guild_only()
    @queue.command(description="📋 Display tracks in the song queue",
                   aliases=["show"],
                   usage="{}queue display")
    async def display(self,ctx):
        queue:SongQueue = ctx.guild.song_queue

        if not queue: 
            raise commands.errors.QueueEmpty("No tracks in the queue for display.")
        
        symbol = "▶︎" if not voice_state.is_paused(ctx.guild) else "\\⏸"
        await ctx.send(embed = discord.Embed(title = f"🎧 Queue | Track Count : {len(queue)} | Full Length : {convert.length_format(queue.total_length)} | Repeat queue : {convert.bool_to_str(queue.queue_looping)}",
                                            #                           **   [Index] if is 1st track [Playing Sign]**    title   (newline)             `Length`               |         @Requester         Do this for every track in the queue
                                            description = "\n".join([f"**{f'[ {i} ]' if i > 0 else f'[{symbol}]'}** {track.title}\n> `{convert.length_format(track.duration)}` | {track.requester.mention}" for i,track in enumerate(list(queue))]),
                                            color=discord.Color.from_rgb(255, 255, 255),
                                            timestamp=datetime.datetime.now()))
    @commands.guild_only()
    @queue.command(aliases=["h"],)
    async def history(self,ctx : commands.Context):
        queue : SongQueue = ctx.guild.song_queue
        history = queue.history
        if not history:
            return await ctx.replywm("History is empty.")
        await ctx.send(embed = discord.Embed(title = f"🎧 Queue history | Track Count : {len(history)}",
                                            description = "\n".join([f"**[-{i} ]** {track.title}\n> `{convert.length_format(track.duration)}` | {track.requester.display_name}" for i,track in enumerate(history[::-1],1)]),
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
                position:int = convert.extract_int_from_str(position)

            except ValueError:

                return await ctx.replywm(f"Please enter a valid number for position.")
            
            else:
                poped_track = queue.get(position)
                
                del queue[position]

                if position == 0 and ctx.voice_client and ctx.voice_client.source:
                    voice_state.replay_track(guild)
                
            
                await ctx.replywm(f"**#{position}** - `{poped_track.title}` has been removed from the queue")
        
    
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

        if removed_index == 0: return await ctx.replywm("None of the track is repeated, therefore no track was removed")

        queue.clear()
        queue.extend(not_rep)

        await ctx.replywm(f"Successfully removed `{removed_index}` duplicated tracks from the queue.")
    
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

        if remove_count == 0: return await ctx.replywm("No requester lefted the voice channel, therefore no track was removed.")

        queue.clear()
        queue.extend(track_in_vc)
        await ctx.replywm(f"Successfully removed `{remove_count}` tracks from the queue.")

    @commands.guild_only()
    @queue.command(description="🧹 Removes every track in the queue or an index onward",
                   aliases=["empty","clr"],
                   usage="{}queue clear")
    async def clear(self,ctx,index = None):
        try:
            index = int(index)
        except ValueError:
            index = None
        queue : SongQueue = ctx.guild.song_queue
        if index is not None:
            remainings = [t for i,t in enumerate(queue) if i <= index]
            queue.clear()
            queue.extend(remainings)
            await ctx.replywm(f"All tracks after `#{index}` is cleared.")
        else:
            queue.clear()
            queue.call_after = lambda: ...
            await ctx.replywm("🗒 The queue has been cleared")
        

    @commands.guild_only()
    @queue.command(description="🔁 Swap the position of two tracks in the queue",
                   usage="{}queue swap 1 2")
    async def swap(self,ctx,position_1,position_2):
        queue:SongQueue = ctx.guild.song_queue

        try: queue.swap(position_1,position_2)
        except (TypeError,IndexError): return await ctx.replywm("❌ Invaild position")

        await ctx.replywm(f"Swapped **#{position_1}** with **#{position_2}** in the queue")

    @commands.guild_only()
    @queue.command(description="🔃 Reverse the position of the whole queue",
                    usage="{}queue reverse")
    async def reverse(self,ctx):
        queue   :SongQueue = ctx.guild.song_queue
        playing :SongTrack = queue.popleft() #We exclude the track playing

        queue.reverse()
        queue.appendleft(playing) #Add the playing track back
        queue.history.pop(-1)
        await ctx.replywm("🔃 The queue has been *reversed*")

    @commands.guild_only()
    @queue.command(description="🎲 Randomize the position of every track in the queue",
                   aliases = ["random","randomize","sfl"],
                   usage="{}queue shuffle")
    async def shuffle(self,ctx):
        queue:SongQueue = ctx.guild.song_queue

        queue.shuffle()

        await ctx.replywm("🎲 The queue has been *shuffled*")

    @commands.guild_only()
    @queue.command(description='🔂 Enable / Disable queue looping.\nWhen enabled, tracks will be moved to the last at the queue after finsh playing',
                   aliases=["loop","looping","repeat_queue",'setloop','setlooping',"toggleloop","toggle_looping",'changelooping','lop'],
                   usage="{}queue repeat on")
    async def repeat(self,
                    ctx:commands.Context,
                    select_mode:str=None):
        guild     :discord.Guild = ctx.guild
        queue     :SongQueue     = guild.song_queue
        new_qloop :bool          = commands.converter._convert_to_bool(select_mode) if select_mode else not queue.queue_looping

        queue.queue_looping = new_qloop
        if not guild.song_queue.audio_message:
            await ctx.replywm(MessageString.queue_loop_audio_msg.format(convert.bool_to_str(new_qloop)))
        await queue.update_audio_message()


    @commands.guild_only()
    @queue.command(description="Enable/Disable auto-playing, which plays recommendation after the last track in the queue ended.")
    async def autoplay(self,ctx:commands.Context,mode:str=None):
        guild     :discord.Guild = ctx.guild
        queue     :SongQueue     = guild.song_queue
        new_qloop :bool          = commands.converter._convert_to_bool(mode) if mode else not queue.auto_play

        queue.auto_play = new_qloop
        await ctx.replywm(f"Auto-playing is switched to {convert.bool_to_str(new_qloop)}")
        await queue.update_audio_message()


    #----------------------------------------------------------------#
    #QUEUE : File 
    @commands.is_owner()
    @queue.command(description='Ouput the queue as a txt file, can be imported again through the import command')
    async def export(self,ctx:commands.Context):
        queue   :SongQueue = ctx.guild.song_queue

        if not queue: 
            raise commands.errors.QueueEmpty("No tracks to export.")

        from io import StringIO
        with StringIO() as queue_file:

            queue_file.name = "queue.txt"
            queue_file.write("+".join([track.webpage_url[32:] for track in queue]))
            queue_file.seek(0)
            await ctx.send(file=discord.File(queue_file),view=View().add_item(Button(label="import to queue",custom_id="import")))

    @commands.is_owner()
    @queue.command(description='Input songs through a txt file, you can also export the current queue with queue export',
                   aliases=["import"],
                   usage="{}queue import [place your txt file in the attachments]")
    async def from_file(self,ctx:commands.Context):
        queue       :SongQueue          = ctx.guild.song_queue
        attachments :discord.Attachment = ctx.message.attachments[0]

        if not attachments: 
            return await ctx.replywm("Please upload a txt file")

        if "utf-8" not in (attachments.content_type): 
            return await ctx.replywm("Invaild file type. (must be txt and utf-8 encoded)")   

        mes :discord.Message = await ctx.replywm("This might take a while ...")
        data:list[str]       = (await attachments.read()).decode("utf-8").split("+")

        for line in data:
            if not line: continue

            try:
                queue.append(await self.bot.loop.run_in_executor(None,
                                                                lambda: SongTrack.create_track(query="https://www.youtube.com/watch?v="+line,
                                                                                                requester=ctx.author,
                                                                                                request_message=mes)))
            except youtube_dl.utils.YoutubeDLError as yt_dl_error:
                await ctx.send(f"Failed to add {line} to the queue because `{yt_dl_error}`")

        await mes.edit(content=f"Successfully added {len(data)-1} tracks to the queue !")
                                
    #----------------------------------------------------------------#
    #EVENTS

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
                            await guild.song_queue.cleanup()
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
        
        try:
            if not (interaction.data["component_type"] == 2 and "custom_id" in interaction.data.keys()):
                return 
        except (AttributeError,KeyError): 
            return

        guild = interaction.guild
        custom_id = interaction.data["custom_id"]

        if logging.root.isEnabledFor(logging.getLevelName("COMMAND_INFO")) and guild.id != 915104477521014834:
            asyncio.create_task(logging.webhook_log(embed= discord.Embed(title = f"{guild.name+' | ' if guild else ''}{interaction.channel}",
                                                                        description = f"**Pressed the {interaction} button**",
                                                                        color=discord.Color.from_rgb(255,255,255),
                                                                        timestamp = datetime.datetime.now()
                                                                        ).set_author(
                                                                        name =interaction.user,
                                                                        icon_url= interaction.user.display_avatar),
                                                    username="Button Logger"))
        
        
        queue : SongQueue = interaction.guild.song_queue

        #Tons of Buttons
        if custom_id == "delete":
            return await interaction.message.delete()

        elif custom_id == "play_again":
            return await MusicButtons.on_play_again_btn_press(interaction,self.bot)

        elif custom_id == "import":
            await interaction.response.defer(thinking=True)
            data : List[str] = (await interaction.message.attachments[0].read()).decode("utf-8").split("+")

            for url in data:
                if not url: 
                    continue

                try:
                    queue.append(await self.bot.loop.run_in_executor(None,
                                                                    lambda: SongTrack.create_track(query="https://www.youtube.com/watch?v="+url,
                                                                                                   requester=interaction.user)))
                except youtube_dl.utils.YoutubeDLError as yt_dl_error:
                    pass
            
            await interaction.followup.send(f"Successful added {len(data)} tracks to the queue")



        if interaction.response.is_done() or guild is None:  
            return print("Responsed")
        # Clearing glitched messages
        elif queue.get(0) is None or queue.audio_message is None or queue.audio_message.id != interaction.message.id or not voice_state.is_playing(guild):
            if not custom_id.isnumeric() and interaction.message.embeds:
                    new_embed:discord.Embed = interaction.message.embeds[0]
                    
                    if len(new_embed.fields) == 9:
                        try:
                            await interaction.response.defer()
                        except (discord.errors.HTTPException,discord.errors.InteractionResponded):
                            pass
                        else:
                            await voice_state.clear_audio_message(specific_message=interaction.message)

    #----------------------------------------------------------------#
    #Utility music commands

    @commands.guild_only()
    @commands.command(aliases=["np", "nowplaying", "now"],
                      description='🔊 Display the current audio playing in the server',
                      usage="{}np")
    async def now_playing(self, ctx:commands.Context):
        

        queue = ctx.guild.song_queue
        audio_message:discord.Message = queue.audio_message
        #No audio playing (not found the now playing message)
        if audio_message is None:
            return await ctx.replywm(MessageString.free_to_use_msg)
        elif ctx.voice_client is None:
            return await ctx.replywm(MessageString.free_to_use_msg + "| not in a voice channel")

        #if same text channel
        if audio_message.channel == ctx.channel:
            return await audio_message.reply("*🎧 This is the audio playing right now ~* [{}/{}]".format(convert.length_format(queue.time_position),
                                                                                                         convert.length_format(queue[0].duration)))
        #Or not
        await ctx.send(f"🎶 Now playing in {voice_state.get_current_vc(ctx.guild).mention} - **{queue[0].title}**")

    @commands.guild_only()
    @commands.command(aliases=["nxtrec"])
    async def nextrecommend(self,ctx:commands.Context):
        queue : SongQueue = ctx.guild.song_queue
        queue._recommendations.rotate(-1)
        await queue.update_audio_message()

    @commands.guild_only()
    @commands.command(aliases=["prevrec"])
    async def previousrecommend(self,ctx:commands.Context):
        queue : SongQueue = ctx.guild.song_queue
        queue._recommendations.rotate(1)
        await queue.update_audio_message()

    @commands.guild_only()
    @commands.command(aliases=["audiomsg"],
                      description="Resend the audio message in the channel and removes the orginal one,",)
    async def resend(self, ctx: commands.Context):
        queue = ctx.guild.song_queue
        audio_msg = queue.audio_message

        if not audio_msg:
            return await ctx.replywm("No audio message present at the moment.")
        
        await voice_state.clear_audio_message(ctx.guild)
        await voice_state.create_audio_message(queue[0],ctx.channel)

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

        proc_mes = await ctx.replywm("Processing ...")
        process = subprocess.Popen(args=["ffmpeg",
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
    #LYRICS COMMAND
    @commands.guild_only()
    @commands.command(aliases=["subtitles"])
    async def lyrics(self,ctx:commands.Context):
        guild = ctx.guild
        queue = guild.song_queue
        current_track = queue[0]
        try:
            subtitle_dict = current_track.subtitles
            if not subtitle_dict:
                raise ValueError
        except (AttributeError,ValueError):
            return await ctx.replywm("Sorry, The song playing now don't have subtitle supported ! (At least not in the youtube caption)") #Current song has no subtitle

        from langcodes import Language
        
        if len(subtitle_dict.keys()) > 1:
            options = []
            for lan in subtitle_dict.keys():
                languageName = Language.get(lan)
                if languageName.is_valid(): 
                    options.append(discord.SelectOption(label=languageName.display_name(), value=lan))
                    if len(options) == 24: 
                        break

            title = current_track.title

            select_language_view = View().add_item(Select(placeholder="Select your language for subtitle", options=options))
            del_msg = await ctx.send(
                content = f"🔠 Select a language for the lyrics of ***{title}***",
                view=select_language_view
            )

            try:
                interaction : Interaction = await self.bot.wait_for(
                    'interaction',
                    check=lambda interaction: interaction.data["component_type"] == 3 and interaction.user.id == ctx.author.id,
                    timeout=TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                return
            await del_msg.delete()
            selected_language = interaction.data["values"][0]
        else: #There is only one language avaiable
            selected_language = list(subtitle_dict.keys())[0]

        modern_lang_name = Language.get(selected_language).display_name()

        url,subtitle_text = Subtitles.extract_subtitles(subtitle_dict,selected_language)
        await ctx.send(
            embed=discord.Embed(title=f"{current_track.title} [{modern_lang_name}]",description=subtitle_text),
            view=UtilityButtons()
        )

    @commands.guild_only()
    @commands.command(aliases=["streamsubtitles"])
    async def streamlyrics(self,ctx:commands.Context):

        ### Get the language for the lyrics
        from langcodes import Language

        guild = ctx.guild
        queue = guild.song_queue
        current_track = queue[0]
        try:
            subtitle_dict = current_track.subtitles
            if not subtitle_dict:
                raise ValueError
        except (AttributeError,ValueError):
            return await ctx.replywm("Sorry, The song playing now don't have subtitle supported ! (At least not in the youtube caption)") #Current song has no subtitle

        
        if len(subtitle_dict.keys()) > 1:
            #Make the language a select_option object
            options = []
            for lan in subtitle_dict.keys():
                languageName = Language.get(lan)
                if languageName.is_valid(): 
                    options.append(discord.SelectOption(label=languageName.display_name(), value=lan))
                    if len(options) == 24: 
                        break

            select_language_view = View().add_item(Select(placeholder="Select your language for subtitle", options=options))
            del_msg = await ctx.send(
                content = f"🔠 Select a language for the lyrics of ***{current_track.title}***",
                view=select_language_view
            )

            #Make the interaction
            try:
                interaction : Interaction = await self.bot.wait_for(
                    'interaction',
                    check=lambda interaction: interaction.data["component_type"] == 3 and interaction.user.id == ctx.author.id,
                    timeout=TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                return
            finally:
                await del_msg.delete()

            selected_language = interaction.data["values"][0]
        else: #There is only one language avaiable, don't even bother asking.
            selected_language = list(subtitle_dict.keys())[0]

        m = await ctx.send(embed=discord.Embed(title="Loading...")) #The message used for displaying lyrics

        ### Getting the subtitle text, using request.
        import requests
        import re

        subtitle_url = current_track.subtitles[selected_language][4]["url"]
        subtitle_content = requests.get(subtitle_url).content.decode("utf-8")
        subr = re.findall(r"^(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\n((^.+\n)+)\n",subtitle_content,re.MULTILINE)
        
        subr = list(map( #Format the time in floating points
            lambda sub:(
                convert.timestr_to_sec_ms(sub[0]),
                convert.timestr_to_sec_ms(sub[1]),
                sub[2]
            )
            ,subr
        )) 

        ### Streaming the lyrics into discord
        from convert import length_format
        from Music import voice_state

        prev_text = ""
        offset = 0.4 # the higher the earilier


        #the stream, a while loop.
        while voice_state.is_playing(queue.guild) and queue.get(0) == current_track and queue.time_position:
            for i,(timing,end_timing,_) in enumerate(subr):

                if timing > queue.time_position + offset and i:
                    text =subr[i-1][2]
                    
                    #Text changed
                    if prev_text != text:
                        prev_text = text
                        await m.edit(embed=discord.Embed(
                            title="Streaming the lyrics",
                            description=text
                        ).set_footer(
                            text=f"{length_format(timing)} - {length_format(end_timing)}"
                        ))

                    break
            
            await asyncio.sleep(0.1)


        await m.edit(embed=discord.Embed(
                        title="The stream ended.",
                        description="..."
                    ),view=UtilityButtons())
        
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
    #             return await ctx.replywm(MessageString.free_to_use_msg)

    #         Track = ctx.guild.song_queue[0]

    #         #Add to the list
    #         position:int = Favourites.add_track(ctx.author, Track.title, Track.webpage_url)

    #         #Responding
    #         await ctx.replywm(MessageString.added_fav_msg.format(Track.title,position))

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
    #             await ctx.replywm("✏ Please enter a vaild index")
    #         except FileNotFoundError:
    #             await ctx.replywm(MessageString.fav_empty_msg)
    #         else: 
    #             await ctx.replywm(f"`{removedTrackTitle}` has been removed from your favourites")
            
    # #Display Favourites

    @commands.command(aliases=["favlist", "myfav"],
                        description='❣🗒 Display every song in your favourites',
                        usage="{}myfav")
    async def display_favourites(self, ctx:commands.Context):
    
        import favourites
        #Grouping the list in string
        try:
            favs_list = favourites.get_data(ctx.author)
        except FileNotFoundError:
            return await ctx.replywm(MessageString.fav_empty_msg)

        wholeList = ""
        for index, title in enumerate(favs_list):
            wholeList += "***{}.*** {}\n".format(index + 1,title)

        #embed =>
        favouritesEmbed = discord.Embed(title=f"🤍 🎧 Favourites of {ctx.author.name} 🎵",
                                        description=wholeList,
                                        color=discord.Color.from_rgb(255, 255, 255),
                                        timestamp=datetime.datetime.now()
                            ).set_footer(text="Your favourites would be the available in every server")

        #sending the embed
        await ctx.replywm(embed=favouritesEmbed)

#END OF COMMANDS
#----------------------------------------------------------------#
async def setup(BOT):
    await BOT.add_cog(MusicCommands(BOT))