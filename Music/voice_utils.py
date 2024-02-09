import discord
import logging

from discord import VoiceClient
from discord.ext import commands
import custom_errors


from typing import TYPE_CHECKING,Union,List
from typechecking import *

if TYPE_CHECKING:
    from .song_queue import SongQueue
    from discord.member import VocalGuildChannel

logger = logging.getLogger(__name__)

#DECORATER
def playing_audio(vcfunc):
    def wrapper(*args,**kwargs):
        guild : discord.Guild = args[0]
        voice_client = ensure_type_optional(guild.voice_client, VoiceClient)

        if voice_client is None:
            raise custom_errors.NotInVoiceChannel(f"Function {vcfunc.__name__} requires the bot to be in a voice channel.")
        if voice_client._player is None: 
            raise custom_errors.NoAudioPlaying(f"Function {vcfunc.__name__} requires the bot to be playing audio.")

        return vcfunc(*args,**kwargs)
      
    return wrapper

def is_paused(guild:discord.Guild,/) -> bool:
    voice_client = ensure_type_optional(guild.voice_client,VoiceClient)
    
    if not voice_client or not voice_client.source:
        return True
    return voice_client.is_paused()


def voice_members(guild:discord.Guild,/) -> List[discord.Member]:
    """Return all the members in a voice channel, not including bots"""
    voice_client = ensure_exist(guild.voice_client, error=custom_errors.NotInVoiceChannel)
    voice_client = ensure_type(voice_client, VoiceClient)

    return [member for member in voice_client.channel.members if not member.bot]



async def join_voice_channel(voice_channel: 'VocalGuildChannel'):
    """Join voice channel, or move to it if already in another one"""
    guild = voice_channel.guild

    #Check permission
    if not list(voice_channel.permissions_for(guild.me))[20][1]:
        raise commands.errors.BotMissingPermissions(["connect"])

    voice_client = ensure_type_optional(guild.voice_client, VoiceClient)

    if voice_client is None: 
        return await voice_channel.connect()
    else:
        voice_client.pause()
        await guild.change_voice_state(channel=voice_channel)
        voice_client.resume()

@playing_audio
def pause_audio(guild:discord.Guild,/):
    voicec = ensure_type(guild.voice_client, VoiceClient)
    voicec.pause()
 
@playing_audio
def resume_audio(guild:discord.Guild,/):
    voicec = ensure_type(guild.voice_client, VoiceClient)
    voicec.resume()

async def clear_audio_message_for(
    target: Union[discord.Message,'SongQueue']
):
    """
    Edit the audio message to give it play again button and make the embed smaller
    """
    from music import SongQueue
    is_queue = isinstance(target, SongQueue)

    # song queue
    if is_queue:
        audio_message = target.audio_message
        
        if audio_message is None:
            return logger.warning("Audio message not found when trying to clean.")
    # message
    else:
        audio_message = target


    # Modifying the embed ~ 
    updated_embed = audio_message.embeds[0].remove_footer()
    updated_embed.description = ''

    for _ in range(8):
        updated_embed.remove_field(2)

    if updated_embed.image:
        updated_embed.set_thumbnail(url=updated_embed.image.url)
        updated_embed.set_image(url=None)

    from my_buttons  import MusicButtons
    await audio_message.edit(
        embed=updated_embed,
        view=MusicButtons.PlayAgainButton
    )
    
    logger.info("Cleared audio messsage.")

    if is_queue: 
        target.audio_message = None

