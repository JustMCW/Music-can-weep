import discord
import time
import asyncio
import logging
import threading

from discord.ext      import commands

import Convert

from main             import BOT_INFO

from Music.song_queue import SongQueue
from Music.song_track import SongTrack

from Buttons          import Buttons
from subtitles        import Subtitles
from Response         import Embeds


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
                raise commands.errors.NoAudioPlaying("Function {vcfunc.__name__} requires the bot to be playing audio.")
        except AttributeError:
            raise commands.errors.NotInVoiceChannel("Function {vcfunc.__name__} requires the bot to be in a voice channel.")
      
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
    return round(guild.song_queue.volume / BOT_INFO.InitialVolume * 100)


def get_non_bot_vc_members(guild:discord.Guild)->list:
    try:
        return [member for member in guild.voice_client.channel.members if not member.bot]
    except AttributeError:
        raise commands.errors.NotInVoiceChannel


async def join_voice_channel(guild:discord.Guild, voice_channel:discord.VoiceChannel):
    if guild.voice_client is None: 
        await voice_channel.connect()
    else: 
        await guild.voice_client.move_to(voice_channel)


@playing_audio
def pause_audio(guild:discord.Guild):
    voice_client:discord.VoiceClient = guild.voice_client
    voice_client.pause()

    #Since the loop count resets after we pause and resume it so we have to save the loop count (basically the time position)
    guild.song_queue.player_loop_passed.append(voice_client._player.loops)

@playing_audio
def resume_audio(guild:discord.Guild):
    guild.voice_client.resume()

@playing_audio
def rewind_audio(guild:discord.Guild):
    guild.song_queue.audio_control_status = "REWIND"
    guild.voice_client.stop()


@playing_audio
def skip_audio(guild:discord.Guild):
    guild.song_queue.audio_control_status = "SKIP"
    guild.voice_client.stop()


@playing_audio
async def restart_audio(guild:discord.Guild,position:float=0):
    queue: SongQueue = guild.song_queue

    if position and position>= queue[0].duration:
        raise IndexError("Seek out of range")

    voice_client:discord.VoiceChannel = guild.voice_client

    queue.audio_control_status = "RESTART"

    voice_client.stop()
    
    abs_loop        :asyncio.AbstractEventLoop  = asyncio.get_running_loop()
    new_start_time  :float                      =float(time.perf_counter())

    queue[0].play(voice_client,
                    volume=queue.volume,
                    after = lambda voice_error: after_playing(abs_loop,
                                                              guild,
                                                              new_start_time,
                                                              voice_error) ,
                    position = position)


def after_playing(event_loop:asyncio.AbstractEventLoop,
                guild:discord.Guild, 
                start_time:float,
                voice_error:str = None):
    """
    if any check 1-3 gives true, stop.
    1. Check for voice error
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
        if voice_error is not None: return logging.error("Voice error :",voice_error)

        voice_client         :discord.VoiceClient = guild.voice_client
        queue                :SongQueue           = guild.song_queue
        audio_control_status :str                 = queue.audio_control_status

        queue.audio_control_status = None
        queue.player_loop_passed.clear()

        #Check stage 1

        #Ensure in voice chat
        if not voice_client or not voice_client.is_connected():
            await clear_audio_message(guild)

            if not queue.enabled:
                queue.popleft()

            await clean_up_queue(guild)

            return logging.info("Ignore loop : NOT IN VOICE CHANNEL")
        
        #Ignore if some commands are triggered
        if audio_control_status == "RESTART":
            return logging.info(f"Ignore loop : RESTART")

        if audio_control_status == "CLEAR":
            await clear_audio_message(guild)

            return logging.info("Ignore loop : CLEAR QUEUE")
        
        #Check stage 2
        FinshedTrack  :SongTrack           = queue[0]
        NextTrack     :SongTrack           = None
        looping       :bool                = queue.looping
        queue_looping :bool                = queue.queue_looping
        text_channel  :discord.TextChannel = queue.audio_message.channel if queue.audio_message else None

        #403 forbidden error (an error that try cannot catch, it makes the audio ends instantly)
        if (time.perf_counter() - start_time) < 0.5 and audio_control_status is None:

            logging.warning(f"Ignore loop : HTTP ERROR, Time (ns) = {time.perf_counter() - start_time}")

            #Get a new piece of info
            NextTrack = SongTrack.create_track(query = FinshedTrack.webpage_url,
                                                requester=FinshedTrack.requester)

            #Replace the old info
            queue[0].formats = NextTrack.formats

        #Single song looping is on
        elif looping and audio_control_status is None:
            NextTrack = FinshedTrack
            threading.Thread(
                target=Subtitles.sync_subtitles,
                args=(queue,text_channel,NextTrack)
            ).start()
        
        #Queuing disabled
        elif not queue.enabled:
            queue.popleft()
            await clear_audio_message(guild)
            return logging.info("Queue disabled")

        #Finshed naturaly / skipped or rewind
        else:
            if audio_control_status == "REWIND": queue.rotate(1)
            elif queue_looping: queue.rotate(-1)    
            else: queue.popleft()

            #Get the next track ( first song in the queue )
            NextTrack = queue.get(0)

            #No song in the queue
            if NextTrack is None:
                # await text_channel.send("\\☑️ All tracks in the queue has been played (if you want to repeat the queue, run \" >>queue repeat on \")",delete_after=30)
                await clear_audio_message(guild)
                return logging.info("Queue is empty")

            #To prevent sending the same audio message again
            if NextTrack != FinshedTrack:
                logging.info(f"Play next track : {NextTrack.title}")

                target = text_channel
                
                if not queue.audio_message.content:
                    #if within 3 message, found the now playing message then use that as the target for editing

                    history = target.history(limit = 3)
                    history = await history.flatten()
                    
                    for msg in history:
                        if msg.id == queue.audio_message.id:
                            target = await target.fetch_message(msg.id)

                if isinstance(target,discord.TextChannel):
                    await clear_audio_message(guild)
                        
                await create_audio_message(Track = NextTrack,
                                                Target = target)
                    
                threading.Thread(
                    target=Subtitles.sync_subtitles,
                    args=(queue,text_channel,NextTrack)
                ).start()
            
            #Skipping the only track in the queue
            elif audio_control_status == "SKIP":
                await text_channel.send("There are no other tracks in queue to be played.")

        
        #Play the audio
        new_start_time =float(time.perf_counter())
        NextTrack.play(voice_client,
                        after=lambda voice_error: after_playing(event_loop,
                                                                    guild,
                                                                    new_start_time,
                                                                    voice_error),
                        volume= queue.volume)

    event_loop.create_task(_async_after())


async def create_audio_message(Track:SongTrack,Target):
    
    """
    Create the discord message for displaying audio playing, including buttons and embed
    """

    #Getting the subtitle
    FoundLyrics :bool          = Subtitles.find_subtitle_and_language(getattr(Track,"subtitles",None))[0]
    guild       :discord.Guild = Target.guild
    queue       :SongQueue     = guild.song_queue

    #the message for displaying and controling the audio
    audio_embed     :discord.Embed = Embeds.audio_playing_embed(queue,FoundLyrics)
    control_buttons :list          = Buttons.AudioControllerButtons
    
    #if it's found then dont disable
    control_buttons[1][2].disabled = not FoundLyrics 

    if isinstance(Target,discord.Message):
        await Target.edit(embed=audio_embed,components=control_buttons)
        Target = await Target.channel.fetch_message(Target.id)

    elif isinstance(Target,discord.TextChannel):
        Target = await Target.send(embed=audio_embed,components=control_buttons)
    
    queue.audio_message = Target


async def clear_audio_message(guild:discord.Guild=None,specific_message:discord.Message = None):

    """
    Edit the audio message to give it play again button and shorten it
    """

    audio_message:discord.Message = specific_message or guild.song_queue.audio_message

    if audio_message is None:  
        return logging.warning("Audio message is none")

    newEmbed:discord.Embed = audio_message.embeds[0]

    for _ in range(4):
        newEmbed.remove_field(2)

    if newEmbed.image:
        newEmbed.set_thumbnail(url=newEmbed.image.url)
        newEmbed.set_image(url=discord.Embed.Empty)
    

    await audio_message.edit(#content = content,
                            embed=newEmbed,
                            components= Buttons.AfterAudioButtons)
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

            new_embed:discord.Embed = audio_msg.embeds[0]
            
            #Replacing the orignal states field
            for _ in range(3):
                new_embed.remove_field(3)


            new_embed.insert_field_at(index=3,
                                    name="🔊 Voice Channel",
                                    value=f"*{get_current_vc(guild).mention}*")
            new_embed.insert_field_at(index=4,
                                    name="📶 Volume",
                                    value=f"`{get_volume_percentage(guild)}%`")
            new_embed.insert_field_at(index=5,
                                    name="🔂 Looping",
                                    value=f"**{Convert.bool_to_str(guild.song_queue.looping)}**")

            #Apply the changes                  
            await audio_msg.edit(embed=new_embed)