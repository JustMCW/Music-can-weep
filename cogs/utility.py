import asyncio
import discord

from discord.ext import commands

import  convert
import music
from music import audio_message
from literals import ReplyStrings

TIMEOUT_SECONDS = 60 * 2


class MusicUtilityCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @commands.guild_only()
    @commands.hybrid_command(
        aliases=["np", "nowplaying", "now"],
        description='🔊 Display the current audio playing in the server',
        usage="{}np"
    )
    async def now_playing(self, ctx: commands.Context):

        queue = music.get_song_queue(ctx.guild)
        audio_message= queue.audio_message
        # No audio playing (not found the now playing message)
        if audio_message is None:
            return await ctx.reply(ReplyStrings.free_to_use_msg)
        elif ctx.voice_client is None:
            return await ctx.reply(ReplyStrings.free_to_use_msg + "| not in a voice channel")

        # if same text channel
        if audio_message.channel == ctx.channel:
            try:
                await audio_message.reply("*🎧 This is the audio playing right now ~* [{}/{}]".format(convert.length_format(queue.time_position),
                                                                                                     convert.length_format(queue[0].duration)))
            except AttributeError:
                await audio_message.reply("🎧 This is track just finshed !")
        # Or not
        else:
            await audio_message.reply(f"Audio playing : {audio_message.jump_url}")

    @commands.guild_only()
    @commands.hybrid_command(aliases=["audiomsg"],
                             description="Resend the audio message in the channel and removes the orginal one.",)
    async def resend(self, ctx: commands.Context):
        queue = music.get_song_queue(ctx.guild)
        audio_msg = queue.audio_message

        if not audio_msg:
            if queue and queue.voice_client and queue.source:
                return await music.create_audio_message(queue, ctx.channel)
            return await ctx.reply("No audio message present at the moment.")

        await audio_message.clear_audio_message_for_queue(queue)
        await music.create_audio_message(queue, ctx.channel)

    @commands.guild_only()
    @commands.hybrid_command(description="Send the current audio as a file which is available for downloading.")
    async def download(self, ctx: commands.Context):
        # i dont want the code to block 
        # but i want to know when the track finished downloading
        # so i decidedd to keep monitoring the size of the file until it remains unchange for a while
        # (not the best solution in the world)

        queue = music.get_song_queue(ctx.guild)
        try:
            playing_track = queue[0]
        except IndexError:
            raise discord.errors.NoAudioPlaying

        source_url: str = playing_track.source_url
        file_name: str = playing_track.title.replace("/", "|") + ".mp3"

        import subprocess
        import os

        proc_mes = await ctx.reply("Processing ...")
        process = subprocess.Popen(
            args=["ffmpeg",
                  "-i", f"{source_url}",
                  '-loglevel', 'warning',
                  # '-ac', '2',
                  f"./{file_name}"
                  ], creationflags=0)
        process.wait()
        cd = 3
        last_progress = 0
        combo = 0
        
        for _ in range(300):
            try:
                progress = os.path.getsize(
                    f'./{file_name}')/playing_track.filesize

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


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicUtilityCommands(bot))
