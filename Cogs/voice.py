"""The commands for joining and leaving voice channels"""

import logging
import asyncio

import discord
from discord.ext import commands
from discord.ui    import View,Button
from discord import ButtonStyle

from music.song_queue import SongQueue
from music import voice_utils

import custom_errors
from literals import ReplyStrings

class VoiceCommands(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot:commands.Bot = bot
        super().__init__()

    @commands.bot_has_guild_permissions(connect=True, speak=True)
    @commands.command(aliases=["enter", "j"],
                      description='🎧 Connect to your current voice channel or a given voice channel name',
                      usage = "{}join Music channel")
    async def join(
        self, 
        ctx:commands.Context,*,
        voice_channel:commands.converter.VoiceChannelConverter=None
    ):
        ctx.bot
        try: 
            voice_channel : discord.VoiceChannel = voice_channel or ctx.author.voice.channel
        except AttributeError: 
            raise custom_errors.UserNotInVoiceChannel("Join a voice channel or specify a voice channel to be joined.")

        if len(voice_channel.members) == 0:
            return await ctx.replywm("Cannot join vc that has no one in it")
        await voice_utils.join_voice_channel(voice_channel)
        await ctx.replywm(ReplyStrings.JOIN(voice_channel))
        queue : SongQueue = ctx.guild.song_queue
        await queue.update_audio_message()

        #Ask the user to resume the queue, if there is.
        if queue:
            message = await ctx.send(
                f"```There are {len(queue)} tracks in the queue, resume ? (Ignore this if no)```",
                view=View().add_item(Button(label="Yes",style=ButtonStyle.green,custom_id="resume_queue"))
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
    @commands.command(aliases=["leave", "bye", 'dis', "lev",'l'],
                      description='👋 Disconnect from the current voice channel i am in',
                      usage="{}leave")
    async def disconnect(self, ctx:commands.Context):
        voice_client = ctx.voice_client

        #Not in a voice channel
        if not voice_client: 
            raise custom_errors.NotInVoiceChannel

        #Disconnect from voice_client
        await voice_client.disconnect()
        await ctx.replywm(ReplyStrings.LEAVE(voice_client.channel))
        
async def setup(bot : commands.Bot):
    await bot.add_cog(VoiceCommands(bot))