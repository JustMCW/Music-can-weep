import discord
import logging

from discord.ext import commands
import custom_errors
from guildext import GuildExt

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .song_queue import SongQueue

logger = logging.getLogger(__name__)

#DECORATER
def playing_audio(vcfunc):
    def wrapper(*args,**kwargs):
        guild : GuildExt = args[0]
        try:
            if guild.voice_client._player: 
                return vcfunc(*args,**kwargs)
            else: 
                raise custom_errors.NoAudioPlaying(f"Function {vcfunc.__name__} requires the bot to be playing audio.")
        except AttributeError as e:
            raise custom_errors.NotInVoiceChannel(f"Function {vcfunc.__name__} requires the bot to be in a voice channel.")
      
    return wrapper

def is_paused(guild:GuildExt,/)->bool:
    if not guild.voice_client or guild.voice_client.source is None:
        return True
    return guild.voice_client.is_paused()

def voice_members(guild:GuildExt,/)->list:
    """Return the members in a voice channel, not including bots"""
    try:
        return [member for member in guild.voice_client.channel.members if not member.bot]
    except AttributeError:
        raise custom_errors.NotInVoiceChannel


async def join_voice_channel(voice_channel:discord.VoiceChannel):
    """Join voice channel, or move to this if already in one"""
    #Check perm
    guild = voice_channel.guild
    if not list(voice_channel.permissions_for(guild.me))[20][1]:
        raise commands.errors.BotMissingPermissions({"connect"})
    if guild.voice_client is None: 
        await voice_channel.connect()
    else:
        guild.voice_client.pause()
        await guild.change_voice_state(channel=voice_channel)

@playing_audio
def pause_audio(guild:GuildExt):
    guild.voice_client.pause()

@playing_audio
def resume_audio(guild:GuildExt):
    guild.voice_client.resume()

async def clear_audio_message(queue:'SongQueue'=None,specific_message:discord.Message = None):
    """
    Edit the audio message to give it play again button and make the embed smaller
    """
    from my_buttons  import MusicButtons

    audio_message:discord.Message = specific_message or queue.audio_message

    if audio_message is None:  
        return logger.info("Audio message is none")

    newEmbed : discord.Embed = audio_message.embeds[0].remove_footer()
    newEmbed.description = ''

    for _ in range(8):
        # if "length" in newEmbed.fields[2].name:
        #     break
        newEmbed.remove_field(2)

    if newEmbed.image:
        newEmbed.set_thumbnail(url=newEmbed.image.url)
        newEmbed.set_image(url=None)
    
    await audio_message.edit(#content = content,
                            embed=newEmbed,
                            view=MusicButtons.PlayAgainButton)
    
    logger.info("Cleared audio messsage.")

    if not specific_message: 
        queue.audio_message = None

