
from discord.ext import commands
from discord import app_commands

import music
from music import MAX_VOLUME_PERCENTAGE
from literals import ReplyStrings

from typechecking import *

class AudioModifierCommands(commands.Cog):
    def __init__(self,bot :commands.Bot ):
        self.bot = bot
        super().__init__()

    @commands.guild_only()
    @commands.hybrid_command(
        aliases=["vol"],
        description=f'📶 set audio volume to a percentage (0% - {MAX_VOLUME_PERCENTAGE}%)',
        usage="{}vol 70"
    )
    @app_commands.describe(volume_percentage="how loud the audio plays [0% - {MAX_VOLUME_PERCENTAGE}%]")
    async def volume(self, ctx: commands.Context, volume_percentage: float):
        
        # Attempt on earraping
        if volume_percentage > MAX_VOLUME_PERCENTAGE and ctx.author.id != ctx.bot.owner_id:
            return await ctx.reply(f"🚫 Please enter a volume below {MAX_VOLUME_PERCENTAGE}% (to protect yours and other's ears 👍🏻)")
        queue = music.get_song_queue(ctx.guild)
        queue.volume_percentage = volume_percentage
        
        await ctx.reply(f"🔊 Volume has been set to {round(volume_percentage,3)}%")
        await music.update_audio_message(queue)

    @commands.guild_only()
    @commands.hybrid_command(
        aliasas=[],
        description="Changes the pitch of the audio playing. ",
        usage="{}pitch 1.1"
    )
    async def pitch(self, ctx:commands.Context, new_pitch: float):

        guild = ensure_exist(ctx.guild)
        queue = music.get_song_queue(guild)
        
        queue.pitch = float(new_pitch)

        if guild.voice_client and queue.source and queue:
            music.pause_audio(guild)
            queue.replay_track()
            
        # if not queue.audio_message:
        await ctx.reply(f"Successful changed the pitch to `{new_pitch}`.")
        await music.update_audio_message(queue)

    @commands.guild_only()
    @commands.hybrid_command(
        aliasas=[],
        description="Changes the tempo of the audio playing",
        usage="{}tempo 1.1"
    )
    @app_commands.describe(new_tempo="how fast the audio plays [0.5 - 5] ( does not affect pitch )")
    async def tempo(self,ctx:commands.Context, new_tempo: float):
        guild =  ensure_exist(ctx.guild)
        queue = music.get_song_queue(ctx.guild)

        if new_tempo <= 0:
            music.pause_audio(guild)
            return await ctx.reply(ReplyStrings.PAUSE)
        elif new_tempo < 0.5 or new_tempo > 5:
            return await ctx.reply("Tempo can only range between `0.5-5`.")

        queue.tempo = float(new_tempo)
        if guild.voice_client and queue.source and queue:
            music.pause_audio(guild)
            queue.replay_track()

        # if not queue.audio_message:
        await ctx.reply(f"Successful changed the tempo to `{new_tempo}`.")
        await music.update_audio_message(queue)

async def setup(bot : commands.Bot):
    await bot.add_cog(AudioModifierCommands(bot))
