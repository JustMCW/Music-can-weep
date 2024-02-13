"""The commands for joining and leaving voice channels"""

import asyncio

from typing import Optional

import discord
from discord.ext import commands
from discord.ui import View, Button
from discord import ButtonStyle

import music

import custom_errors
from literals import ReplyStrings
from keys import *
from typechecking import *


class VoiceCommands(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: commands.Bot = bot
        super().__init__()

    # @commands.bot_has_guild_permissions(connect=True, speak=True)
    @commands.guild_only()
    @commands.hybrid_command(
        aliases=["enter", "j"],
        description='🎧 Connect to your current voice channel or a given voice channel name',
        usage="{}join Music channel"
    )
    async def join(
        self,
        ctx: commands.Context, *,
        voice_channel: Optional[discord.VoiceChannel] = None
    ):
        if voice_channel is None: 
            user_voice = ctx.author.voice
            if user_voice is None:
                raise custom_errors.UserNotInVoiceChannel("Join a voice channel or specify a voice channel to be joined.")
            voice_channel =  user_voice.channel

        if len(voice_channel.members) == 0:
            return await ctx.reply("Cannot join vc that has no one in it")

        await music.join_voice_channel(voice_channel)
        await ctx.reply(ReplyStrings.JOIN.format(voice_channel))
        queue = music.get_song_queue(ctx.guild)
        await music.update_audio_message(queue)

        # Ask the user to resume the queue, if there is.
        if queue:
            message = await ctx.send(
                f"```There are {len(queue)} tracks in the queue, resume ? (Ignore this if no)```",
                view=View().add_item(Button(label="Yes", style=ButtonStyle.green, custom_id="resume_queue"))
            )

            try:
                await self.bot.wait_for(
                    "interaction",
                    timeout=20,
                    check=lambda interaction:
                        interaction.data["component_type"] == 2 and
                        "custom_id" in interaction.data.keys() and
                        interaction.message.id == message.id and
                        interaction.user.id == ctx.author.id
                )
            except asyncio.TimeoutError:
                pass
            else:
                await ctx.invoke(self.bot.get_command('resume'))
            finally:
                await message.delete()

    @commands.guild_only()
    @commands.hybrid_command(aliases=["disconnect", "bye", 'dis', "lev", 'l'],
                             description='👋 Disconnect from the current voice channel i am in',
                             usage="{}leave")
    async def leave(self, ctx: commands.Context):
        voice_client = ctx.voice_client
        
        if not voice_client:
            raise custom_errors.NotInVoiceChannel

        await voice_client.disconnect(force=False)
        await ctx.reply(ReplyStrings.LEAVE.format(voice_client.channel))


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceCommands(bot))
