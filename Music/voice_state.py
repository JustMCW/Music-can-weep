from typing import Union
import discord
import logging

from discord.ext      import commands
from .song_queue import SongQueue,SongTrack

from my_buttons       import MusicButtons
from string_literals  import MyEmojis
import Convert

def AudioPlayingEmbed(queue : SongQueue) -> discord.Embed:
    """the discord embed for displaying the audio that is playing"""
    current_track = queue.current_track

    if not current_track:
        return print("No track is in the queue, thus unable to create an embed for it.")

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
                        value=f'`{Convert.length_format(getattr(current_track,"duration"))}`')\
            .add_field(name="📝 Lyrics",
                        value=f"*Available in {len(current_track.subtitles)} languages*" if getattr(current_track,"subtitles",None) else "*Unavailable*")\
            \
            .add_field(name="📶 Volume ",
                        value=f"`{queue.volume_percentage}%`")\
            .add_field(name="⏩ Tempo",
                        value=f"`{queue.tempo:.2f}`")\
            .add_field(name="ℹ️ Pitch",
                        value=f'`{queue.pitch:.2f}`')\
            \
            .add_field(name="🔊 Voice Channel",
                        value=f"{queue.guild.voice_client.channel.mention}")\
            .add_field(name="🔂 Looping",
                        value=f'**{Convert.bool_to_str(queue.looping)}**')\
            .add_field(name="🔁 Queue looping",
                        value=f'**{Convert.bool_to_str(queue.queue_looping)}**')
    if queue.get(1):
        rembed.set_footer(text=f"Next track : {queue[1].title}",icon_url=queue[1].thumbnail)
    elif queue.auto_play and not queue.queue_looping:
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
        guild.voice_client.pause()
        await guild.change_voice_state(channel=voice_channel)


@playing_audio
def pause_audio(guild:discord.Guild):
    voice_client:discord.VoiceClient = guild.voice_client
    voice_client.pause()

@playing_audio
def resume_audio(guild:discord.Guild):
    guild.voice_client.resume()

def shift_track(guild:discord.Guild, count=1):
    queue = guild.song_queue
    async def rotate_queue():
        queue.rotate(count * -1)
        queue.play_first()
        await queue.make_next_audio_message()

    queue.call_after = rotate_queue
    guild.voice_client.stop()

def rewind_track(guild:discord.Guild, count=1):
    """Add the latest history track to the front of the queue for an ammount, 
    does not raise any error when paramater `count` is greater than the length of the queue history"""
    queue : SongQueue = guild.song_queue
    if queue.queue_looping and queue[-1].source:
        return shift_track(guild, count * -1)
    async def rewind_after():
        for _ in range(count):
            try: queue.appendleft(queue.history.pop(-1))
            except IndexError: break
        queue.play_first()
        await queue.make_next_audio_message()

    queue.call_after = rewind_after
    guild.voice_client.stop()

def skip_track(guild:discord.Guild, count=1):
    queue : SongQueue = guild.song_queue
    if queue.queue_looping:
        return shift_track(guild, count)
    async def skip_after():
        for _ in range(count):
            try: queue.poplefttohistory()
            except IndexError: break 
        if queue.current_track:
            queue.play_first()
            await queue.make_next_audio_message()

    queue.call_after = skip_after 
    guild.voice_client.stop()

def replay_track(guild:discord.Guild):
    queue : SongQueue = guild.song_queue 
    queue.call_after = lambda: queue.play_first()
    guild.voice_client.stop()

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
        "view": MusicButtons.AudioControllerButtons(queue)
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
    
    await audio_message.edit(#content = content,
                            embed=newEmbed,
                            view=MusicButtons.PlayAgainButton)
    
    logging.info("Succesfully removed audio messsage.")

    if not specific_message: 
        guild.song_queue.audio_message = None



