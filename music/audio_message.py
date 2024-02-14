import asyncio
import logging
import discord
import math

import convert
from literals import MyEmojis,ReplyStrings
from my_buttons import MusicButtons

from .song_track import YoutubeTrack,WebFileTrack,WebsiteSongTrack
from .voice_constants import UPDATE_DELAY, PROGRESSBAR_SIZE


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .song_queue import SongQueue
    
    
logger = logging.getLogger(__name__)

### Audio messages

def audio_display_embed(queue : 'SongQueue') -> discord.Embed:
    """returns  discord embed for displaying the audio that is playing"""
    if not queue.voice_client:
        raise RuntimeError("Attempted to create an audio_message while not connected to a voice channel")
    
    current_track = queue[0]

    #Init embed + requester header + thumbnail
    rembed = discord.Embed( title= current_track.title,
                            url= current_track.webpage_url or current_track.source_url,
                            color=discord.Color.from_rgb(255, 255, 255) ) \
            .set_author(name=f"Requested by {current_track.requester.display_name}" ,
                        icon_url=current_track.requester.display_avatar ) \
            .set_image( url=current_track.thumbnail )

    # Creator field
    if isinstance(current_track,WebsiteSongTrack):

        if isinstance(current_track,YoutubeTrack):
            #Author field
            channel,channel_url = current_track.channel
            rembed.add_field(
                name=f"{MyEmojis.youtube_icon} YT channel",
                value=f"[{channel}]({channel_url})"
            )

        else:
            uploader, uploader_url = current_track.uploader
            rembed.add_field(
                name=f"💡 Creator",
                value=f"[{uploader}]({uploader_url})"
            )

    duration_formmated = convert.length_format(current_track.duration) if current_track.duration else "N/A"
    # File size field
    if isinstance(current_track, WebFileTrack):
        rembed.add_field(
            name=f"File format",
            value=f"{current_track.file_format}"
        ).add_field(
            name=f"File size",
            value=f"{current_track.file_size}"
        )
    else:
        rembed.add_field(name="↔️ Length",
                         value=f'`{duration_formmated}`')
    
    subtitles = getattr(current_track,"subtitles",None)
    rembed.add_field(name="📝 Lyrics",
                     value=f"*Available in {len(subtitles)} languages*" if subtitles else "*Unavailable*")
        
    emoji_before = "━" or '🟥' 
    emoji_mid = "●"
    emoji_after = "━" or '⬜️'
    #Durartion field + Progress bar
    
    
    
    if current_track.duration:
        try:
            progress = max(
                math.floor(
                    (queue.time_position / current_track.duration) * PROGRESSBAR_SIZE
                ),
                1
            )
        except AttributeError:
            progress = 1

        progress_bar = (emoji_before * (progress-1)) + emoji_mid + emoji_after * (PROGRESSBAR_SIZE-progress)
        
        
        
        
        
        rembed.set_footer(text=f"{convert.length_format(int(queue.time_position))} [ {progress_bar} ] {duration_formmated}")


    # General stuff
    rembed.add_field(
        name="📶 Volume ",
        value=f"`{queue.volume_percentage}%`"
    ).add_field(
        name="⏩ Tempo",
        value=f"`{queue.tempo:.2f}`"
    ).add_field(
        name="ℹ️ Pitch",
        value=f'`{queue.pitch:.2f}`'
    )
    
    
    
    rembed.add_field(
        name="🔊 Voice Channel",
        value=f"{queue.voice_client.channel.mention}"
    ).add_field(
        name="🔂 Looping",
        value=f'**{ReplyStrings.prettify_bool(queue.looping)}**' 
    ).add_field(
        name="🔁 Queue looping",
        value=f'**{ReplyStrings.prettify_bool(queue.queue_looping)}**'
    )
            
    if queue.get(1):
        rembed.add_field(
            name="🎶 Upcoming track",
            value=queue[1].title
        )
    elif queue.auto_play and isinstance(current_track, YoutubeTrack) and not queue.queue_looping:
        rembed.add_field(
            name="🎶 Upcoming track (Auto play)",
            value= current_track.recommend.title
        )

    return rembed

async def create_audio_message(
    queue: 'SongQueue',
    target: discord.abc.Messageable | discord.Message
):
    """
    Create the discord message for displaying audio playing, including buttons and embed
    accecpt a text channel or a message to be edited
    """
    if not queue.current_track:
        return 
    

    message_info = {
        "embed": audio_display_embed(queue),
        "view" : MusicButtons.AudioControllerButtons(queue)
    }


    if isinstance(target,discord.Message):
        await target.edit(**message_info)
        queue.audio_message = await target.channel.fetch_message(target.id)

    elif isinstance(target,discord.TextChannel):
        queue.current_track.request_message
        try:
            queue.audio_message = await target.send(**message_info)
        except discord.errors.Forbidden:
            channels = [ 
                chan
                for chan in await target.guild.fetch_channels()
                if  isinstance(chan,discord.TextChannel)
            ]
            queue.audio_message = await channels[-1].send(**message_info)
    else:
        raise ValueError("Unhandled type passed in create_audio_message function")
    #A thread that keeps updating the audio progress bar until the audio finishs
    t = queue[0]

    if not t.duration: 
        return 

    async def run():
        while queue.get(0) == t: 

            if not queue[0].source:
                await asyncio.sleep(UPDATE_DELAY)
                continue

            if not queue.guild.voice_client:
                break

            if not queue.guild.voice_client.is_paused(): #type: ignore
                await update_audio_message(queue)

            await asyncio.sleep(UPDATE_DELAY)

        logger.info("Exited update loop")

    queue._event_loop.create_task(run())


async def make_next_audio_message(queue: 'SongQueue'):
    """Remove the current audio message and make a new one, can be editing or sending a new one."""

    audio_message = queue.audio_message
    if not audio_message:
        return logger.warning("No audio message")

    next_track = queue.current_track

    is_reply = audio_message.reference

    if next_track:

        if audio_message.embeds[0].url == next_track.webpage_url:
            return logger.debug("Track is the same, not updating")
        
        if (queue.looping or queue.queue_looping):

            if not is_reply:
                if next_track.request_message:
                    await clear_audio_message(next_track.request_message)
                    next_track.request_message = None
                return await create_audio_message(queue,audio_message)
    
    await clear_audio_message_for_queue(queue)
    
    if next_track:
        
        if next_track.request_message:
            await create_audio_message(queue,next_track.request_message)   
            next_track.request_message = None
        elif is_reply:
            await create_audio_message(queue,audio_message.channel) #type: ignore
        else:
            await create_audio_message(queue, audio_message)

async def update_audio_message(queue: 'SongQueue'):
    audio_msg = queue.audio_message

    if not audio_msg: 
        return logger.warning("Audio message adsent when trying to update it.")


    await audio_msg.edit(
        embed = audio_display_embed(queue),
        view = MusicButtons.AudioControllerButtons(queue)
    )


async def clear_audio_message(audio_message: discord.Message):
    """Clears the message directly, does not require the queue"""
    updated_embed = audio_message.embeds[0].remove_footer()
    updated_embed.description = ''

    for _ in range(8):
        updated_embed.remove_field(2)

    if updated_embed.image:
        updated_embed.set_thumbnail(url=updated_embed.image.url)
        updated_embed.set_image(url=None)

    await audio_message.edit(
        embed=updated_embed,
        view=MusicButtons.PlayAgainButton
    )

async def clear_audio_message_for_queue(
    target: 'SongQueue'
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
    await clear_audio_message(audio_message)
    
    logger.info("Cleared audio messsage.")

    if is_queue: 
        target.audio_message = None

