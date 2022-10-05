from typing import Union
import discord
import asyncio
import logging

from discord.ext      import commands

from main             import BotInfo

from Music.song_queue import SongQueue,AudioControlState
from Music.song_track import SongTrack,AutoPlayUser

from my_buttons          import MusicButtons
from string_literals         import MyEmojis
import convert

def AudioPlayingEmbed(queue : SongQueue) -> discord.Embed:
    """the discord embed for displaying the audio that is playing"""
    from Music import voice_state
    
    current_track = queue[0]

    YT_creator = getattr(current_track,"channel",None) 
    Creator = YT_creator or getattr(current_track,"uploader")
    Creator_url = getattr(current_track,"channel_url",getattr(current_track,"uploader_url",None))
    Creator = "[{}]({})".format(Creator,Creator_url) if Creator_url else Creator

    rembed = discord.Embed(title= current_track.title,
                        url= current_track.webpage_url,
                        color=discord.Color.from_rgb(255, 255, 255))\
            \
            .set_author(name=f"Requested by {current_track.requester.display_name}",
                        icon_url=current_track.requester.display_avatar)\
            .set_image(url = current_track.thumbnail)\
            \
            .add_field(name=f"{MyEmojis.YOUTUBE_ICON} YT channel" if YT_creator else "💡 Creator",
                        value=Creator)\
            .add_field(name="↔️ Length",
                        value=f'`{convert.length_format(getattr(current_track,"duration"))}`')\
            .add_field(name="📝 Lyrics",
                        value=f"*Available in {len(current_track.subtitles)} languages*" if getattr(current_track,"subtitles",None) else "*Unavailable*")\
            \
            .add_field(name="📶 Volume ",
                        value=f"`{voice_state.get_volume_percentage(queue.guild)}%`")\
            .add_field(name="⏩ Tempo",
                        value=f"`{queue.tempo:.2f}`")\
            .add_field(name="ℹ️ Pitch",
                        value=f'`{queue.pitch:.2f}`')\
            \
            .add_field(name="🔊 Voice Channel",
                        value=f"{queue.guild.voice_client.channel.mention}")\
            .add_field(name="🔂 Looping",
                        value=f'**{convert.bool_to_str(queue.looping)}**')\
            .add_field(name="🔁 Queue looping",
                        value=f'**{convert.bool_to_str(queue.queue_looping)}**')
    if queue.get(1):
        rembed.set_footer(text=f"Next track : {queue[1].title}",icon_url=queue[1].thumbnail)
    elif queue.auto_play:
        rembed.set_footer(text=f"Auto-play : {queue.recommend.title}",icon_url=queue.recommend.thumbnail)
    return rembed

def is_playing(guild:discord.Guild)-> bool:
    if not guild.voice_client: 
        return False
    return guild.voice_client.source is not None

#DECORATER
def playing_audio(vcfunc):
    def wrapper(*args,**kwargs):
        guild = args[-1] if isinstance(args[-1],discord.Guild) else kwargs.get("guild")
        try:
            if guild.voice_client._player: 
                return vcfunc(*args,**kwargs)
            else: 
                raise commands.errors.NoAudioPlaying(f"Function {vcfunc.__name__} requires the bot to be playing audio.")
        except AttributeError:
            raise commands.errors.NotInVoiceChannel(f"Function {vcfunc.__name__} requires the bot to be in a voice channel.")
      
    return wrapper


def is_paused(guild:discord.Guild)->bool:
    if not is_playing(guild):
        return True
    return guild.voice_client.is_paused()


def get_current_vc(guild:discord.Guild)->discord.VoiceChannel:
    try:
        return guild.voice_client.channel
    except AttributeError:
        return None


def get_volume_percentage(guild:discord.Guild)->int:
    return round(guild.song_queue.volume / BotInfo.InitialVolume * 100)


def get_non_bot_vc_members(guild:discord.Guild)->list:
    try:
        return [member for member in guild.voice_client.channel.members if not member.bot]
    except AttributeError:
        raise commands.errors.NotInVoiceChannel


async def join_voice_channel(guild:discord.Guild, voice_channel:discord.VoiceChannel):
    #Check perm
    if not list(voice_channel.permissions_for(guild.me))[20][1]:
        raise commands.errors.BotMissingPermissions({"connect"})
    if guild.voice_client is None: 
        await voice_channel.connect()
    else: 
        await guild.change_voice_state(channel=voice_channel)



@playing_audio
def pause_audio(guild:discord.Guild):
    voice_client:discord.VoiceClient = guild.voice_client
    voice_client.pause()

@playing_audio
def resume_audio(guild:discord.Guild):
    guild.voice_client.resume()

@playing_audio
def rewind_track(guild:discord.Guild):
    guild.song_queue.audio_control_status = AudioControlState.REWIND
    guild.voice_client.stop()


@playing_audio
def skip_track(guild:discord.Guild):
    guild.song_queue.audio_control_status = AudioControlState.SKIP
    guild.voice_client.stop()


@playing_audio
async def restart_track(guild:discord.Guild):
    queue: SongQueue = guild.song_queue

    voice_client:discord.VoiceChannel = guild.voice_client

    queue.audio_control_status = AudioControlState.RESTART

    voice_client.stop()

def after_playing(event_loop:asyncio.AbstractEventLoop,
                guild:discord.Guild, 
                voice_error:str = None):
    """
    if any check 1-3 gives true, stop.
    1. Check for voice error (like audio file broke)
    2. Check if the bot is in a voice channel
    3. Check for trigger, whether the restart/clear command is used

    For checks 4-7 here, if one occured, finsh its proccess and skip to [8]
    4. Check for 403 forbidden error, re-extract the info for the track
    5. Check for single looping
    6. Queue disabled, STOP CONTINUE
    7. Finshed without interruption :
    
    8. Create the audio message indicating the audio
    9. Sync the subtitle
    10. Play song track
    11. Recursion after finsh playing (back to step 1) until it stop
    """
    async def _async_after():
        #warning : You are about to enter the most chaotic code in my whole project.
        if voice_error is not None: return logging.error("Voice error :",voice_error)

        voice_client         :discord.VoiceClient = guild.voice_client
        queue                :SongQueue           = guild.song_queue
        audio_control_status :str                 = queue.audio_control_status
        

        queue.audio_control_status = None
        FinshedTrack  :SongTrack           = queue[0]
        #I moved it here because cleanup runs after the this function in the orginal code, and we need the cleanup function to access the return code
        FinshedTrack.source.original.cleanup() 
        returncode = FinshedTrack.source.original.returncode
        # try:
        #     print(queue.time_position*queue.tempo,queue[0].duration)
        #     print(audio_control_status)
        # except: ...
        #Check stage 1
        #Ensure in voice chat
        if not voice_client or not voice_client.is_connected():
            await clear_audio_message(guild)

            if not queue.enabled:
                queue.popleft()

            await clean_up_queue(guild)

            return logging.info("Ignore loop : NOT IN VOICE CHANNEL")
        
        #Ignore if some commands are triggered
        if audio_control_status == AudioControlState.RESTART:
            return queue.play_first(voice_client)

        if audio_control_status == AudioControlState.CLEAR:
            queue.clear()
            await clear_audio_message(guild)

            return logging.info("Ignore loop : CLEAR QUEUE")
        
        #Check stage 2
        NextTrack     :SongTrack           = None
        looping       :bool                = queue.looping
        queue_looping :bool                = queue.queue_looping
        text_channel  :discord.TextChannel = queue.audio_message.channel if queue.audio_message else None

        #403 forbidden error (most like to be it)
        if returncode == 1:

            #Get a new piece of info
            NextTrack = SongTrack.create_track(query = FinshedTrack.webpage_url,
                                                requester=FinshedTrack.requester,
                                                request_message=FinshedTrack.request_message)

            #Replace the old info
            queue[0].formats = NextTrack.formats

        #Single song looping is on
        elif looping and audio_control_status is None:
            NextTrack = FinshedTrack
        
        #Queuing disabled
        elif not queue.enabled:
            queue.popleft()
            await clear_audio_message(guild)
            return logging.info("Queue disabled")

        #Finshed naturaly / skipped or rewind
        else:

            queue[0].request_message = None
            
            if audio_control_status == AudioControlState.REWIND: queue.appendleft(queue.history.pop(-1))
            elif queue_looping: queue.rotate(-1)    
            else: queue.popleft()
            
            #Make the history
            if audio_control_status != AudioControlState.REWIND:
                queue.history.append(FinshedTrack)

            #Get the next track ( first song in the queue )
            NextTrack = queue.get(0)

            #No song in the queue
            if NextTrack is None:
                if queue.auto_play:
                    next_url = queue.recommend.url
                    NextTrack = SongTrack.create_track(query=next_url,requester=AutoPlayUser)
                    queue.append(NextTrack)
                else:
                    # await text_channel.send("\\☑️ All tracks in the queue has been played (if you want to repeat the queue, run \" >>queue repeat on \")",delete_after=30)
                    await clear_audio_message(guild)
                    return logging.info("Queue is empty")
            elif len(queue) == 1:
                queue.generate_rec()

            #To prevent sending the same audio message again
            if NextTrack != FinshedTrack:
                logging.info(f"Play next track : {NextTrack.title}")
                target = text_channel
                

                is_first_msg_a_requesting = True #Sadly can't use enumerate
                async for msg in target.history(limit = 3):
                    
                    if NextTrack.request_message:
                        #if the request message is the first message, make it one
                        if msg.id == NextTrack.request_message.id and is_first_msg_a_requesting:
                            target = NextTrack.request_message
                            break
                    is_first_msg_a_requesting = False

                    if msg.id == queue.audio_message.id:
                        
                        #if within 3 message, found the now playing message then use that as the target for editing
                        if queue.audio_message.reference is None:
                            target = await target.fetch_message(msg.id)
                        
                    
                
                if isinstance(target,discord.TextChannel) or (is_first_msg_a_requesting and NextTrack.request_message): #
                    await clear_audio_message(guild)
                        
                await create_audio_message(Track = NextTrack,
                                            Target = target)
            
            #Skipping the only track in the queue
            elif audio_control_status == AudioControlState.SKIP:
                await text_channel.send("There are no other tracks in queue to be played.")

        
        #Play the audio
        queue.play_first(voice_client)

    event_loop.create_task(_async_after())


async def create_audio_message(Track:SongTrack,Target:Union[discord.TextChannel,discord.Message]):
    
    """
    Create the discord message for displaying audio playing, including buttons and embed
    accecpt a text channel or a message to be edited
    """

    #Getting the subtitle
    guild       :discord.Guild = Target.guild
    queue       :SongQueue     = guild.song_queue

    message_info = {
        "embed": AudioPlayingEmbed(queue),
        "view": MusicButtons.AudioControllerButtons()
    }

    if isinstance(Target,discord.Message):
        await Target.edit(**message_info)
        queue.audio_message = await Target.channel.fetch_message(Target.id)

    elif isinstance(Target,discord.TextChannel):

        try:
            if Track.request_message.channel.id == Target.id:
                queue.audio_message = await Track.request_message.reply(**message_info)
            else:
                raise AttributeError("Not the same channel.")
        except (AttributeError):
            queue.audio_message = await Target.send(**message_info)
    


async def clear_audio_message(guild:discord.Guild=None,specific_message:discord.Message = None):

    """
    Edit the audio message to give it play again button and make the embed smaller
    """
    audio_message:discord.Message = specific_message or guild.song_queue.audio_message

    if audio_message is None:  
        return logging.warning("Audio message is none")

    newEmbed : discord.Embed = audio_message.embeds[0].remove_footer()

    for _ in range(7):
        newEmbed.remove_field(2)

    if newEmbed.image:
        newEmbed.set_thumbnail(url=newEmbed.image.url)
        newEmbed.set_image(url=None)
    
    audio_message.components
    await audio_message.edit(#content = content,
                            embed=newEmbed,
                            view=MusicButtons.PlayAgainButton)
    logging.info("Succesfully removed audio messsage.")

    if not specific_message: guild.song_queue.audio_message = None


async def clean_up_queue(guild:discord.Guild):
    queue:SongQueue = guild.song_queue
    clear_after = 600

    if queue and queue.guild.database.get("auto_clear_queue"):
        logging.info(f"Wait for {clear_after} sec then clear queue")
        await asyncio.sleep(clear_after)
        
        voice_client:discord.VoiceClient = guild.voice_client
        if not voice_client or not voice_client.is_connected():
            if len(queue) != 0:
                queue.clear()


async def update_audio_msg(guild):
    """
    Updates the audio message's embed (volume, voice channel, track looping)
    """

    if is_playing(guild): 

        audio_msg:discord.Message = guild.song_queue.audio_message

        if audio_msg: 
            from my_buttons import MusicButtons
            #Apply the changes                  
            await audio_msg.edit(
                embed= AudioPlayingEmbed(guild.song_queue),
                view = MusicButtons.AudioControllerButtons()
            )