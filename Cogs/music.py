#Built-ins
import asyncio
import logging

import os
import datetime
from typing    import List,Tuple

#Third party libaries
import youtube_dl

import discord
from discord.ext   import commands
from discord.ui    import View,Select,Button


#My own modules
import convert
import database.user_playlist as playlistdb
import custom_errors

# from subtitles        import Subtitles

from music.song_queue import SongQueue
from music.song_track import TrackDomain,SongTrack,create_track_from_url
from music.voice_constants import *
from music         import voice_utils
from my_buttons    import MusicButtons,UtilityButtons
from youtube_utils import YoutubeVideo,url_matcher,search_from_youtube

from guildext import GuildExt
from webhook_logger import *
from guildext import GuildExt

#Literals
from literals import ReplyStrings, MyEmojis
#----------------------------------------------------------------#
TIMEOUT_SECONDS         = 60 * 2
logger = logging.getLogger(__name__)
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
        self.bot:commands.Bot = bot

        super().__init__()

    #----------------------------------------------------------------#
    #INTERRUPTING THE AUDIO

    @commands.guild_only()
    @commands.command(aliases=["wait"],
                      description='⏸ Pause the current audio',
                      usage="{}pause")
    async def pause(self, ctx:commands.Context):
        voice_utils.pause_audio(ctx.guild)
        await ctx.replywm(ReplyStrings.PAUSE)
        
    @commands.guild_only()
    @commands.command(aliases=["continue", "unpause"],
                      description='▶️ Resume the current audio',
                      usage="{}resume")
    async def resume(self, ctx:commands.Context):
        """
        Note : This is not exactly the opposite of pausing.

        Resume the player.
        
        However if the player is not found,
        join a voice channel (if not already in one) and play the first track in the queue.
        """

        guild:GuildExt     = ctx.guild
        queue:SongQueue         = guild.song_queue      
        current_track:SongTrack = queue.current_track

        #Try to resume the audio like usual
        try:
            voice_utils.resume_audio(guild)
        #Error encountered, player is not found
        except (custom_errors.NotInVoiceChannel,custom_errors.NoAudioPlaying) as resume_error: 
            
            #Stop if there is no track in the queue at all
            if not current_track:
                raise custom_errors.NoAudioPlaying

            #Check for voice
            if isinstance(resume_error,custom_errors.NotInVoiceChannel):
                try:
                    await voice_utils.join_voice_channel(ctx.author.voice.channel)
                except AttributeError:
                    raise resume_error

            #Play the track
            await queue.create_audio_message(await ctx.send("▶️ Continue to play tracks in the queue"))

            queue.play_first()
        
        #Successfully resumed like usual, send response.
        else:
            await ctx.replywm(ReplyStrings.RESUME)       

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
            raise custom_errors.NoAudioPlaying
        
        guild   :GuildExt = ctx.guild
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
            raise custom_errors.NoAudioPlaying
        
        guild   :GuildExt = ctx.guild
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
            voice_utils.pause_audio(ctx.guild)
            queue.time_position = position_sec
            voice_utils.resume_audio(ctx.guild)
            await ctx.replywm(f"*⏏️ Moved the time position to * `{convert.length_format(position_sec)}`")


    @commands.guild_only()
    @commands.command(aliases=["replay", "re"],
                      description='🔄 restart the current audio track, equivalent to seeking to 0',
                      usage="{}replay")
    async def restart(self, ctx:commands.Context):
        ctx.guild.song_queue.time_position = 0
        await ctx.replywm(ReplyStrings.RESTART)

    #----------------------------------------------------------------#
    #SEEKING THOUGHT THE SONG QUEUE
    @commands.guild_only()
    @commands.command(aliases=["last","prev"],
                      description="⏪ Return to the previous song played",
                      usage="{}prev 1")
    async def previous(self, ctx:commands.Context,count = 1):
        try: count = int(count)
        except ValueError: count = 1
        guild : GuildExt = ctx.guild
        guild.song_queue.rewind_track(count)
        await ctx.send("Rewinded.")
       
            
    @commands.guild_only()
    @commands.command(aliases=['next',"nxt"],
                      description='⏩ skip to the next track in the queue',
                      usage="{}skip 1")
    async def skip(self, ctx:commands.Context,count = 1):
        try: count = int(count)
        except ValueError: count = 1

        guild : GuildExt = ctx.guild
        guild.song_queue.skip_track(count)
        await ctx.replywm(ReplyStrings.SKIP)    

    @commands.guild_only()
    @commands.command(aliases=["rotate","shf"],
                      description='⏩ skip to the next track and move it to the back of the queue, you can enter negative number to make it shift backward (move last track to the fist)')
    async def shift(self,ctx:commands.Context,count = 1): 
        try: count = int(count)
        except ValueError: count = 1

        guild : GuildExt = ctx.guild
        guild.song_queue.shift_track(count)
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
        if volume_percentage > MAX_VOLUME_PERCENTAGE and ctx.author.id != ctx.bot.owner_id:
            return await ctx.replywm(f"🚫 Please enter a volume below {MAX_VOLUME_PERCENTAGE}% (to protect yours and other's ears 👍🏻)")

        guild       :GuildExt       = ctx.guild
        guild.song_queue.volume_percentage = volume_percentage
        
        # if not guild.song_queue.audio_message:
        await ctx.replywm(f"🔊 Volume has been set to {round(volume_percentage,3)}%")
        await guild.song_queue.update_audio_message()

    @commands.guild_only()
    @commands.command(aliasas=[],
                      description="Changes the pitch of the audio playing. ",
                      usage="{}pitch 1.1")
    async def pitch(self, ctx:commands.Context, new_pitch):

        guild : GuildExt = ctx.guild
        queue = guild.song_queue
        try:
            if float(new_pitch) <= 0:
                raise ValueError

            #speed / pitch >= 0.5
            queue.pitch = float(new_pitch)
        except ValueError:
            return await ctx.replywm("Invalid pitch.")
        if guild.voice_client and guild.voice_client._player and queue:
            voice_utils.pause_audio(guild)
            queue.replay_track()
            
        if not guild.song_queue.audio_message:
            await ctx.replywm(f"Successful changed the pitch to `{new_pitch}`.")
        await queue.update_audio_message()

    commands.guild_only()
    @commands.command(aliasas=[],
                      description="Changes the tempo of the audio playing, can range between `0.5` - `5` ",
                      usage="{}tempo 1.1")
    async def tempo(self,ctx:commands.Context, new_tempo):
        guild : GuildExt = ctx.guild
        queue = guild.song_queue

        try:
            new_tempo = float(new_tempo)
            if new_tempo <= 0:
                voice_utils.pause_audio(guild)
                return await ctx.replywm(ReplyStrings.PAUSE)
            elif new_tempo < 0.5 or new_tempo > 5:
                return await ctx.replywm("Tempo can only range between `0.5-5`.")

            queue.tempo = new_tempo
        except ValueError:
            return await ctx.replywm("Invalid tempo.")
        if guild.voice_client and guild.voice_client._player and queue:
            queue.replay_track()

        if not queue.audio_message:
            await ctx.replywm(f"Successful changed the tempo to `{new_tempo}`.")
        await queue.update_audio_message()


    @commands.guild_only()
    @commands.command(aliases=["looping","repeat"],
                      description='🔂 Enable / Disable single audio track looping\nWhen enabled tracks will restart after playing',
                      usage="{}loop on")
    async def loop(self, ctx:commands.Context, mode=None):
        guild   : GuildExt = ctx.guild
        new_loop: bool          = commands.converter._convert_to_bool(mode) if mode else not guild.song_queue.looping

        guild.song_queue.looping = new_loop

        await ctx.replywm(ReplyStrings.TRACK_LOOP(new_loop))
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
                   query:str = None, #URL / Favourite track index / Keyword
                   _btn: discord.Interaction=None # This will be present if this command was invoked from a play_again button
    ):
        if not query:
            attachments = ctx.message.attachments
            import inspect
            if not attachments:
                raise commands.errors.MissingRequiredArgument(commands.Parameter(name="query",kind=inspect.Parameter.POSITIONAL_OR_KEYWORD))
            attachment = attachments[0]
            query = attachment.url
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
        
        guild       : GuildExt       = ctx.guild
        author      : discord.Member      = getattr(_btn,"user",ctx.author)
        voice_client: discord.VoiceClient = ctx.voice_client or author.voice #It can be either the bot's vc or the user's vc
        reply_msg   : discord.Message     = None  #This will be the message for the audio message

        # Check for voice channel
        if voice_client is None:
            # Send a interaction respond instead
            if _btn:
                return await _btn.response.send_message(content=ReplyStrings.user_not_in_vc_msg,ephemeral=True)
            raise custom_errors.UserNotInVoiceChannel("You need to be in a voice channel.")

        destination_url = query

        url_match = url_matcher(query)

        if url_match:
            # Triggered by play_again button (so it must already be a valid URL because it was played successfully before )            
            if _btn:
            #Suppress the interaction failed message and response 
                await _btn.response.edit_message(content=_btn.message.content)
                reply_msg = await ctx.replywm(content=f"🎻 {author.display_name} requests to play this song again")
            # From a URL
            else:
                message = None
                emoji = {
                    TrackDomain.YOUTUBE : MyEmojis.youtube_icon,
                    TrackDomain.SOUNDCLOUD : "☁️",
                    TrackDomain.DISCORD_ATTACHMENT : "🔵",
                }

                for domain in list(TrackDomain):
                    if url_match["domain"] == domain.value:
                        message = f"{emoji.get(domain,'🎵')} A {domain.value.capitalize()} URL is selected"

                if not message:
                    return await ctx.send("Oops ! Only Youtube and Soundcloud links are supported ! ")

                reply_msg = await ctx.replywm(content=message)
                

        # From keyword
        else:
            # Get the search result
            try:
                search_result = search_from_youtube(query,ResultLengthLimit=5)
            except IndexError:
                return await ctx.replywm(f"No search result was found for `{query}` ...")

            choice_message = await ctx.replywm(**generate_search_result_attachments(search_result))
            
            # Get which video the user wish to play

            try:
                choice_interaction: discord.Interaction = await ctx.bot.wait_for(
                    "interaction",
                    timeout = TIMEOUT_SECONDS,
                    # Make sure that it is the user we want who presses the button
                    check   = lambda interaction: 
                        interaction.data["component_type"] == 2 and
                        "custom_id" in interaction.data.keys()  and
                        interaction.message.id == choice_message.id
                )
            
            # Timeouted
            except asyncio.TimeoutError:
                return await choice_message.edit(
                    view = None, # Remove the buttons
                    embed = discord.Embed(
                        title       = f"{MyEmojis.cute_panda} No track was selected !",
                        description = f"You thought for too long ( {int(TIMEOUT_SECONDS/60)} minutes ), use the command again !",
                        color       = discord.Color.from_rgb(255, 255, 255)
                    )
                )

            # Received option
            selected_index = int(choice_interaction.data["custom_id"])

            await choice_interaction.response.edit_message(content=f"{MyEmojis.youtube_icon} Song **#{selected_index+1}** in the youtube search result has been selected",view = None)
            reply_msg = await ctx.fetch_message(choice_message.id)
            destination_url = f'https://www.youtube.com/watch?v={search_result[selected_index].videoId}'
            logging.info(f"Selected {destination_url}")


    ### We now have the exact url that lead us to the audio regardless of what the user've typed, 
    ### Let's extract the audio and play it.
        
        queue = guild.song_queue


        # Extract & create the song track
        try:
            NewTrack = create_track_from_url(
                url=destination_url,
                requester=author,
            )
            

        # Extraction Failed
        except youtube_dl.utils.YoutubeDLError as yt_dl_error:
            logger.warning(yt_dl_error.__class__.__name__)

            utils = youtube_dl.utils

            for error,error_message in {
                utils.UnsupportedError      : "Sorry, this url is not supported !",
                utils.UnavailableVideoError : "Video was unavailable",
                utils.DownloadError         : str(yt_dl_error).replace("ERROR: ",""),
            }.items():
                if isinstance(yt_dl_error,error):
                    return await reply_msg.reply(f"An error occurred : {error_message}")

            # Raise the error if it wasn't in the above dictionary
            # since I'm not too sure what else could cause the error
            logger.error(yt_dl_error)
            raise yt_dl_error

        # Extraction was Successful
        else:

            # Stop current audio if queuing is disabled
            if guild.voice_client: 
                if not queue.enabled:
                    guild.voice_client.stop()
                    # Idk, wait for the track to be popped ?
                    while queue.current_track:
                        await asyncio.sleep(1)

            # Joining the voice channel
            else: 
                #User left during the loading was taking place
                if not author.voice:
                    return await reply_msg.edit(content = "User left the voice channel, the track was cancled.")

                await voice_utils.join_voice_channel(author.voice.channel)
                
            queue.append(NewTrack)

            # There is a track playing already
            if queue.get(1) and queue.enabled:

                await reply_msg.edit(
                    embed=discord.Embed(
                        title = NewTrack.title,
                        url=NewTrack.webpage_url,
                        description="Has been added to the queue.",
                        color=discord.Color.from_rgb(255, 255, 255),
                    ).add_field(
                        name="Length ↔️",
                        value=f"`{convert.length_format(NewTrack.duration)}`",
                    ).add_field(
                        name = "Position in queue 🔢",
                        value=len(queue)-1,
                    ).set_thumbnail(
                        url = NewTrack.thumbnail,
                    )
                )

                # Since there is a field in the audio message indcating the next track
                await queue.update_audio_message() 
                
                # we still want to play the first track
                NewTrack.request_message = await ctx.fetch_message(reply_msg.id)

                if voice_client.source:
                    return

                reply_msg = None
                NewTrack = queue[0]

            # #Make our audio message
            await queue.create_audio_message(reply_msg or ctx.channel)

            # Let ffmpeg initialize itself
            # await asyncio.sleep(1.5)
            
            # Playing the first track in queue 
            try:
                queue.play_first()
            
            # Happens when 2 user try to play tracks at the same time, or something else idk
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

    @commands.guild_only()
    @commands.command(aliases=["pf"],
                      description="Play your attachement file")
    async def play_file(self,ctx:commands.Context):
        attach = ctx.message.attachments[0]
        if "audio" not in attach.content_type:
            return await ctx.reply(f"File attachement must be an audio file, not {attach.content_type} file.")

        t = SongTrack.from_attachment(attach,ctx.author)
        q = ctx.guild.song_queue
        q.append(t)
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()
        q.play_first()
        await q.create_audio_message(ctx.channel)

    #----------------------------------------------------------------#
    
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
                if not voice_utils.voice_members(guild):
                    logger.info("Nobody is in vc with me")

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
                        if voice_client and not voice_utils.voice_members(guild):
                            await guild.song_queue.cleanup()
                    except custom_errors.NotInVoiceChannel:
                        pass
        #---------------------#
        #Bot moved channel
        elif member == self.bot.user:
            if before.channel and after.channel:
                if before.channel.id != after.channel.id: #Moving channel
                    if voice_client:
                        logger.info("Pasued because moved")
                        guild.voice_client.pause()



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
            return await ctx.replywm(ReplyStrings.free_to_use_msg)
        elif ctx.voice_client is None:
            return await ctx.replywm(ReplyStrings.free_to_use_msg + "| not in a voice channel")

        #if same text channel
        if audio_message.channel == ctx.channel:
            try:
                await audio_message.reply("*🎧 This is the audio playing right now ~* [{}/{}]".format(convert.length_format(queue.time_position),
                                                                                                         convert.length_format(queue[0].duration)))
            except AttributeError:
                await audio_message.reply("🎧 This is track just finshed !")
        #Or not
        else:
            await audio_message.reply(f"Audio playing : {audio_message.jump_url}")
             
            # await ctx.send(f"🎶 Now playing in {ctx.voice_client.channel.mention} - **{queue[0].title}**")

    @commands.guild_only()
    @commands.command(aliases=["nxtrec"])
    async def nextrecommend(self,ctx:commands.Context):
        queue : SongQueue = ctx.guild.song_queue
        queue[0].recommendations.rotate(-1)
        await queue.update_audio_message()

    @commands.guild_only()
    @commands.command(aliases=["prevrec"])
    async def previousrecommend(self,ctx:commands.Context):
        queue : SongQueue = ctx.guild.song_queue
        queue[0].recommendations.rotate(1)
        await queue.update_audio_message()

    @commands.guild_only()
    @commands.command(aliases=["audiomsg"],
                      description="Resend the audio message in the channel and removes the orginal one,",)
    async def resend(self, ctx: commands.Context):
        queue = ctx.guild.song_queue
        audio_msg = queue.audio_message

        if not audio_msg:
            return await ctx.replywm("No audio message present at the moment.")
        
        await voice_utils.clear_audio_message(queue)
        await queue.create_audio_message(ctx.channel)

    @commands.guild_only()
    @commands.command(description="Send the current audio as a file which is available for downloading.")
    async def download(self,ctx:commands.Context):
        queue = ctx.guild.song_queue
        try:
            playing_track : SongTrack = queue[0]
        except IndexError:
            raise discord.errors.NoAudioPlaying

        source_url:str = playing_track.source_url
        file_name:str = playing_track.title.replace("/","|") + ".mp3"
        
        import subprocess

        proc_mes = await ctx.replywm("Processing ...")
        process = subprocess.Popen(args=["ffmpeg",
                    "-i",f"{source_url}",
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
                interaction : discord.Interaction = await self.bot.wait_for(
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
        from subtitles import Subtitles
        url,subtitle_text = Subtitles.extract_subtitles(subtitle_dict,selected_language)
        try:
            await ctx.send(
                embed=discord.Embed(title=f"{current_track.title} [{modern_lang_name}]",description=subtitle_text),
                view=UtilityButtons()
            )
        except discord.HTTPException as httpe:
            await ctx.send(f"Unable to send subtitle, [{httpe.code}], sourcelink : {url}")

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
                interaction : discord.Interaction = await self.bot.wait_for(
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
    
        import database.user_playlist as user_playlist
        #Grouping the list in string
        try:
            favs_list = user_playlist.get_data(ctx.author)
        except FileNotFoundError:
            return await ctx.replywm(ReplyStrings.fav_empty_msg)

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