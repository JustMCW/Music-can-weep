from discord.ext import commands

import music
from typechecking import *
from literals import ReplyStrings

class AutoPlayCommands(commands.Cog):

    

    @commands.guild_only()
    @commands.hybrid_group(
        description="Enable/Disable auto-playing, which plays recommendation after the last track in the queue ended."
    )
    async def autoplay(self,ctx:commands.Context):
        await self.toggle(ctx)
        
    @commands.guild_only()
    @autoplay.command(
        description="Enable/Disable auto-playing, which plays recommendation after the last track in the queue ended."
    )
    async def toggle(self, ctx:commands.Context, mode: Optional[bool] = None):
        queue = music.get_song_queue(ctx.guild)
        queue.auto_play = not queue.auto_play if mode is None else mode

        await ctx.reply(f"Auto-playing is switched to {ReplyStrings.prettify_bool(queue.auto_play)}")
        await queue.update_audio_message()

    @commands.guild_only()
    @autoplay.command(
        description="Changes the setting of the recommendation, such as no repeat."
    )
    async def configure(self, ctx:commands.Context):
        # queue = music.get_song_queue(ctx.guild)

        await ctx.reply(f"Unfinished")

    @commands.guild_only()
    @autoplay.command(
        aliases=["nxtrec"],
        description="pick the next recommended track, requires autoplay to be enabled"
    )
    async def nextrecommend(self,ctx:commands.Context):
        queue = music.get_song_queue(ctx.guild)
        track = queue[0]

        if not isinstance(track,music.YoutubeTrack):
            return await ctx.reply("Recommendation is only supported for Youtube Videos.")

        track.recommendations.rotate(-1)
        await queue.update_audio_message()

    @commands.guild_only()
    @autoplay.command(
        aliases=["prevrec"],
        description="pick the last recommended track, requires autoplay to be enabled"
    )
    async def previousrecommend(self,ctx:commands.Context):
        queue = music.get_song_queue(ensure_exist(ctx.guild))
        track = queue[0]

        if not isinstance(track,music.YoutubeTrack):
            return await ctx.reply("Recommendation is only supported for Youtube Videos.")
        
        track.recommendations.rotate(-1)
        await queue.update_audio_message()

async def setup(bot : commands.Bot):
    await bot.add_cog(AutoPlayCommands())