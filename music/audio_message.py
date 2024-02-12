import asyncio
import logging

import discord

from .voice_constants import UPDATE_DELAY

logger = logging.getLogger(__name__)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .song_queue import SongQueue

### Audio messages


async def create_audio_message(queue: 'SongQueue',
    target: discord.abc.Messageable | discord.Message
):
    """
    Create the discord message for displaying audio playing, including buttons and embed
    accecpt a text channel or a message to be edited
    """
    if not queue.current_track:
        return 
    
    from my_buttons import MusicButtons
    from literals   import ReplyEmbeds

    message_info = {
        "embed": ReplyEmbeds.audio_displayer(queue),
        "view" : MusicButtons.AudioControllerButtons(queue)
    }


    if isinstance(target,discord.Message):
        await target.edit(**message_info)
        queue.audio_message = await target.channel.fetch_message(target.id)

    if isinstance(target,discord.TextChannel):
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

    from my_buttons import MusicButtons
    from literals   import ReplyEmbeds

    await audio_msg.edit(
        embed = ReplyEmbeds.audio_displayer(queue),
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

    from my_buttons  import MusicButtons
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
    print(audio_message)
    await clear_audio_message(audio_message)
    
    logger.info("Cleared audio messsage.")

    if is_queue: 
        target.audio_message = None

