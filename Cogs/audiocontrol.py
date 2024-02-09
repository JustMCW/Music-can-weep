from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from music import voice_utils
import music

from literals import ReplyStrings
import custom_errors

from typechecking import *

import convert
from convert import TimeConverter

class AudioControllerCommands(commands.Cog):
    def __init__(self,bot :commands.Bot ):
        self.bot = bot
        super().__init__()

    #----------------------------------------------------------------#

    @commands.guild_only()
    @commands.hybrid_command(
        aliases=["wait"],
        description='⏸ Pause the current audio',
        usage="{}pause"
    )
    async def pause(self, ctx:commands.Context):
        voice_utils.pause_audio(ctx.guild)
        await ctx.reply(ReplyStrings.PAUSE)
        
    @commands.guild_only()
    @commands.hybrid_command(
        aliases=["continue", "unpause"],
        description='▶️ Resume the current audio',
        usage="{}resume"
    )
    async def resume(self, ctx:commands.Context):
        """
        Note : This is not exactly the opposite of pausing.

        Resume the player.
        
        However if the player is not found,
        join a voice channel (if not already in one) and play the first track in the queue.
        """

        guild = ensure_exist(ctx.guild)
        queue = music.get_song_queue(guild)     
        current_track  = queue.current_track

        #Try to resume the audio like usual
        try:
            voice_utils.resume_audio(guild)
        #Error encountered, player is not found
        except (custom_errors.NotInVoiceChannel,custom_errors.NoAudioPlaying) as resume_error: 
            
            #Stop if there is no track in the queue at all
            if not current_track:
                raise custom_errors.NoAudioPlaying

            #Check for voice
            if isinstance(resume_error,custom_errors.NotInVoiceChannel):
                try:
                    await voice_utils.join_voice_channel(ctx.author.voice.channel)
                except AttributeError:
                    raise resume_error

            #Play the track
            await queue.create_audio_message(await ctx.send("▶️ Continue to play tracks in the queue"))

            queue.play_first()
        
        #Successfully resumed like usual, send response.
        else:
            await ctx.reply(ReplyStrings.RESUME)       

    #----------------------------------------------------------------#
    #SEEKING THROUGHT THE AUDIO
    @commands.guild_only()
    @commands.hybrid_command(
        aliases=["fast_forward","fwd"],
        description = "⏭ Fast-foward the time position of the current audio for a certain amount of time.",
        usage="{0}fwd 10\n{0}foward 10:30"
    )
    async def forward(self, ctx, *, time: TimeConverter):
        """
        Fast-foward the player by time given by the user
        """
        voicec:discord.VoiceClient = ctx.voice_client

        if voicec is None or not voicec.is_playing(): 
            raise custom_errors.NoAudioPlaying
        
        guild = ctx.guild
        queue = music.get_song_queue(guild)

        if queue[0].duration < (time + queue.time_position):
            await ctx.reply("Ended the current track")
            return voicec.stop()

        voicec.pause()
        queue.time_position += time
        voicec.resume()

        await ctx.reply(f"*⏭ Fast-fowarded for * `{convert.length_format(time)}`")

    @commands.guild_only()
    @commands.hybrid_command(
        aliases=["rwd"],
        description = "⏭ Fast-foward the time position of the current audio for a certain amount of time.",
        usage="{0}fwd 10\n{0}foward 10:30"
    )
    async def rewind(self, ctx, *, time: TimeConverter):
        """
        Rewind the player by time given by the user
        """
        voicec : discord.VoiceClient = ctx.voice_client

        if voicec is None or not voicec.is_playing(): 
            raise custom_errors.NoAudioPlaying
        
        guild = ctx.guild
        queue = music.get_song_queue(guild)
        queue[0].time_position -= time / queue.tempo

        await ctx.reply(f"*⏮ Rewinded for * `{convert.length_format(time)}`")

    @commands.guild_only()
    @commands.hybrid_command(
        aliases=["jump"],
        description="⏏️ Move the time position of the current audio",
        usage="{}seek 2:30"
    )
    @app_commands.describe(time="Format : [hours:minutes:seconds]")
    async def seek(self, ctx:commands.Context, *, time: TimeConverter):
        await ctx.defer()
        queue = music.get_song_queue(ctx.guild)

        if not queue.current_track:
            raise custom_errors.NoAudioPlaying

        voice_utils.pause_audio(ctx.guild)
        queue.time_position = time
        voice_utils.resume_audio(ctx.guild)
        await ctx.reply(f"*⏏️ Moved the time position to * `{convert.length_format(time)}`")

    @commands.guild_only()
    @commands.hybrid_command(
        aliases=["replay", "re"],
        description='🔄 restart the current audio track, equivalent to seeking to 0',
        usage="{}replay"
    )
    async def restart(self, ctx:commands.Context):
        music.get_song_queue(ctx.guild).time_position = 0
        await ctx.reply(ReplyStrings.RESTART)

    @commands.guild_only()
    @commands.hybrid_command(
        description='⏹ stop the audio from playing 🚫',
        usuge="{}stop"
    )
    async def stop(self, ctx:commands.Context):
        queue = music.get_song_queue(ctx.guild)
        voice_client = ensure_type_optional(ctx.voice_client,discord.VoiceClient)
        if voice_client:
            queue._call_after = lambda: queue.clear()
            await voice_client.disconnect()
        else:
            queue.clear()
        
        return await ctx.send("Stopped & emptied the queue.")
      
    @commands.guild_only()
    @commands.hybrid_command(
        aliases=["looping","repeat"],
        description='🔂 Enable / Disable single audio track looping.',
        usage="{}loop on"
    )
    async def loop(self, ctx:commands.Context, mode: Optional[bool] = None):
        queue = music.get_song_queue(ctx.guild)
        print(queue.looping)
        queue.looping = not queue.looping if mode is None else mode
        await ctx.reply(ReplyStrings.TRACK_LOOP(queue.looping))
        await queue.update_audio_message()

async def setup(bot : commands.Bot):
    await bot.add_cog(AudioControllerCommands(bot))