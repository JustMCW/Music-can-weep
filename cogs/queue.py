from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Select, Button

import music
from music import SongQueue, SongTrack, create_track_from_url
from music import voice_utils

import convert
import custom_errors
import datetime

from literals import ReplyStrings
from functools import reduce

# QUEUE


class QueueCommands(commands.Cog):

    def __init__(self, bot) -> None:
        self.bot: commands.Bot = bot
        super().__init__()

    @commands.guild_only()
    @commands.hybrid_command(
        aliases=["last", "prev"],
        description="⏪ Return to the previous song played",
        usage="{}prev 1"
    )
    async def previous(self, ctx: commands.Context, count: int = 1):
        music.get_song_queue(ctx.guild).rewind_track(count)
        await ctx.send("Rewinded.")

    @commands.guild_only()
    @commands.hybrid_command(
        aliases=['next', "nxt"],
        description='⏩ skip to the next track in the queue',
        usage="{}skip 1"
    )
    async def skip(self, ctx: commands.Context, count: int = 1):
        try:
            count = int(count)
        except ValueError:
            count = 1

        music.get_song_queue(ctx.guild).skip_track(count)
        await ctx.reply(ReplyStrings.SKIP)

    @commands.guild_only()
    @commands.hybrid_command(
        aliases=["rotate", "shf"],
        description='⏩ move track(s) at the front to the back of the queue'
    )
    async def shift(self, ctx: commands.Context, count: int = 1):

        music.get_song_queue(ctx.guild).shift_track(count)
        await ctx.reply(":arrows_counterclockwise:  Shifted.")

    @commands.guild_only()
    @commands.hybrid_group(
        description="🔧 You can manage the song queue with this group of command",
        aliases=["que", "qeueu", "q"],
        usage="{0}queue display\n{0}q clear"
    )
    async def queue(self, ctx: commands.Context):

        guild = ctx.guild

        if not music.get_song_queue(ctx.guild).enabled:
            raise custom_errors.QueueDisabled(
                "Queuing is disabled in {0}.".format(guild.name))

        if ctx.invoked_subcommand is None:
            def get_params_str(cmd) -> str:
                if list(cmd.clean_params):
                    return f"`[{']` `['.join(list(cmd.clean_params))}]`"
                return ""

            await ctx.reply(embed=discord.Embed(title="Queue commands :",
                                                description="\n".join(
                                                    [f"{ctx.prefix}queue **{cmd.name}** {get_params_str(cmd)}" for cmd in ctx.command.walk_commands()]),
                                                color=discord.Color.from_rgb(255, 255, 255)))

    @commands.guild_only()
    @queue.command(
        description="📋 Display tracks in the song queue",
        aliases=["show"],
        usage="{}queue display"
    )
    async def display(self, ctx):
        queue: SongQueue = music.get_song_queue(ctx.guild)

        if not queue:
            raise custom_errors.QueueEmpty(
                "No tracks in the queue for display.")

        symbol = "▶︎" if not voice_utils.is_paused(ctx.guild) else "\\⏸"
        await ctx.send(embed=discord.Embed(title=f"🎧 Queue | Track Count : {len(queue)} | Full Length : {convert.length_format(queue.total_length)} | Repeat queue : {ReplyStrings.prettify_bool(queue.queue_looping)}",
                                           #                           **   [Index] if is 1st track [Playing Sign]**    title   (newline)             `Length`               |         @Requester         Do this for every track in the queue
                                           description="\n".join(
                                               [f"**{f'[ {i} ]' if i > 0 else f'[{symbol}]'}** {track.title}\n> `{convert.length_format(track.duration)}` | {track.requester.mention}" for i, track in enumerate(list(queue))]),
                                           color=discord.Color.from_rgb(
                                               255, 255, 255),
                                           timestamp=datetime.datetime.now()))

    @commands.guild_only()
    @queue.command(aliases=["h"],)
    async def history(self, ctx: commands.Context):
        queue: SongQueue = music.get_song_queue(ctx.guild)
        history = queue.history
        if not history:
            return await ctx.reply("History is empty.")
        # basically displaying the track 
        await ctx.send(embed=discord.Embed(title=f"🎧 Queue history | Track Count : {len(history)}",
                                           description="\n".join(
                                               [f"**[-{i} ]** {track.title}\n> `{convert.length_format(track.duration)}` | {track.requester.display_name}" for i, track in enumerate(history[::-1], 1)]),
                                           color=discord.Color.from_rgb(
                                               255, 255, 255),
                                           timestamp=datetime.datetime.now()))

    @commands.guild_only()
    @queue.group(
        description=" Remove one song track by position in the queue",
        aliases=["rm", "delete", "del"],
        usage="{0}queue remove 1\n{0}q rm dup"
    )
    async def remove(self, ctx: commands.Context):

        queue = music.get_song_queue(ctx.guild)

        if not queue:
            raise custom_errors.QueueEmpty(
                "There must be songs in the queue to be removed.")

        if ctx.invoked_subcommand is None:
            # Removing by position

            position: str = ctx.subcommand_passed

            if not position:
                raise commands.errors.MissingRequiredArgument("position")

            try:
                position: int = convert.extract_int_from_str(position)

            except ValueError:

                return await ctx.reply(f"Please enter a valid number for position.")

            else:
                poped_track = queue.get(position)

                del queue[position]

                if position == 0 and ctx.voice_client and ctx.voice_client.source:
                    queue.replay_track()

                await ctx.reply(f"**#{position}** - `{poped_track.title}` has been removed from the queue")

    @commands.guild_only()
    @remove.command(description="Remove tracks which are duplicated in the queue",
                    aliases=["dup", "repeated"],
                    usage="{}queue remove duplicate")
    async def duplicated(self, ctx):

        queue: SongQueue = music.get_song_queue(ctx.guild)
        not_rep: list[SongTrack] = []

        def is_dup(appeared: list, item: SongTrack):
            if item.webpage_url not in appeared:
                appeared.append(item.webpage_url)
                not_rep.append(item)
            return appeared

        reduce(is_dup, queue, [])
        removed_index: int = len(queue) - len(not_rep)

        if removed_index == 0:
            return await ctx.reply("None of the track is repeated, therefore no track was removed")

        queue.clear()
        queue.extend(not_rep)

        await ctx.reply(f"Successfully removed `{removed_index}` duplicated tracks from the queue.")

    @commands.guild_only()
    @remove.command(description="Remove tracks which their requester is not in the bot's voice channel",
                    aliases=["left_vc", "left"],
                    usage="{}queue remove left")
    async def left_user(self, ctx: commands.Context):

        guild = ctx.guild
        queue: SongQueue = music.get_song_queue(ctx.guild)
        user_in_vc: list[discord.Member] = voice_utils.voice_members()
        user_in_vc_ids: list[int] = map(lambda mem: mem.id, user_in_vc)
        track_in_vc: list[SongQueue] = filter(
            lambda t: t.requester.id in user_in_vc_ids, queue)
        remove_count: int = len(queue) - len(track_in_vc)

        if remove_count == 0:
            return await ctx.reply("No requester lefted the voice channel, therefore no track was removed.")

        queue.clear()
        queue.extend(track_in_vc)
        await ctx.reply(f"Successfully removed `{remove_count}` tracks from the queue.")

    @commands.guild_only()
    @queue.command(description="🧹 Removes every track in the queue or an index onward",
                   aliases=["empty", "clr"],
                   usage="{}queue clear")
    async def clear(self, ctx, index=-1):
        try:
            index = int(index)
        except (ValueError):
            return
        queue: SongQueue = music.get_song_queue(ctx.guild)

        if index >= 0:
            remainings = [t for i, t in enumerate(queue) if i <= index]
            queue.clear()
            queue.extend(remainings)
            await ctx.reply(f"All tracks after `#{index}` is cleared.")
        else:
            queue.clear()
            queue._call_after = lambda: ...
            await ctx.reply("🗒 The queue has been cleared")

    @commands.guild_only()
    @queue.command(description="🔁 Swap the position of two tracks in the queue",
                   usage="{}queue swap 1 2")
    async def swap(self, ctx, position_1, position_2):
        queue: SongQueue = music.get_song_queue(ctx.guild)

        try:
            queue.swap(position_1, position_2)
        except (TypeError, IndexError):
            return await ctx.reply("❌ Invaild position")

        await ctx.reply(f"Swapped **#{position_1}** with **#{position_2}** in the queue")

    @commands.guild_only()
    @queue.command(description="🔃 Reverse the position of the whole queue",
                   usage="{}queue reverse")
    async def reverse(self, ctx):
        queue: SongQueue = music.get_song_queue(ctx.guild)
        playing: SongTrack = queue.popleft()  # We exclude the track playing

        queue.reverse()
        queue.appendleft(playing)  # Add the playing track back
        queue.history.pop(-1)
        await ctx.reply("🔃 The queue has been *reversed*")

    @commands.guild_only()
    @queue.command(description="🎲 Randomize the position of every track in the queue",
                   aliases=["random", "randomize", "sfl"],
                   usage="{}queue shuffle")
    async def shuffle(self, ctx: commands.Context):
        queue = music.get_song_queue(ctx.guild)

        queue.shuffle()

        await ctx.reply("🎲 The queue has been *shuffled*")

    @commands.guild_only()
    @queue.command(description='🔂 When enabled, tracks will be moved to the last at the queue after finsh playing',
                   aliases=["loop", "looping", "repeat_queue", 'setloop', 'setlooping',
                            "toggleloop", "toggle_looping", 'changelooping', 'lop'],
                   usage="{}queue repeat on")
    async def repeat(self, ctx: commands.Context, mode: Optional[bool] = None):
        
        queue: SongQueue = music.get_song_queue(ctx.guild)
        new_qloop: bool = commands.converter._convert_to_bool(mode) if mode else not queue.queue_looping
        
        queue.queue_looping = new_qloop
        if not queue.audio_message:
            await ctx.reply(ReplyStrings.QUEUE_LOOP(new_qloop))
        await music.update_audio_message(queue)

    #----------------------------------------------------------------#

    @commands.is_owner()
    @queue.command(description='Ouput the queue as a txt file, can be imported again through the import command')
    async def export(self, ctx: commands.Context):
        queue: SongQueue = music.get_song_queue(ctx.guild)

        if not queue:
            raise custom_errors.QueueEmpty("No tracks to export.")

        from io import StringIO
        with StringIO() as queue_file:

            queue_file.name = "queue.txt"
            queue_file.write(
                "+".join([track.webpage_url[32:] for track in queue]))
            queue_file.seek(0)
            await ctx.send(file=discord.File(queue_file), view=View().add_item(Button(label="import to queue", custom_id="import")))

    @commands.is_owner()
    @queue.command(description='Input songs through a txt file, from the export command',
                   aliases=["import"],
                   usage="{}queue import [place your txt file in the attachments]")
    async def from_file(self, ctx: commands.Context):
        import youtube_dl

        queue: SongQueue = music.get_song_queue(ctx.guild)
        attachments: discord.Attachment = ctx.message.attachments[0]

        if not attachments:
            return await ctx.reply("Please upload a txt file")

        if "utf-8" not in (attachments.content_type):
            return await ctx.reply("Invaild file type. (must be txt and utf-8 encoded)")

        mes: discord.Message = await ctx.reply("This might take a while ...")
        data: list[str] = (await attachments.read()).decode("utf-8").split("+")

        for line in data:
            if not line:
                continue

            try:
                t = create_track_from_url(
                    url="https://www.youtube.com/watch?v="+line,
                    requester=ctx.author,
                )
            except youtube_dl.utils.YoutubeDLError as yt_dl_error:
                await ctx.send(f"Failed to add {line} to the queue because `{yt_dl_error}`")
            else:
                queue.append(t)
        await mes.edit(content=f"Successfully added {len(data)-1} tracks to the queue !")


async def setup(BOT):
    await BOT.add_cog(QueueCommands(BOT))
