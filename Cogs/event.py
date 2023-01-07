import json
import os
import logging
import discord

from discord.ext import commands, tasks
from literals    import ReplyStrings

import database.server as serverdb
import custom_errors

import key
import webhook_logger

from guildext import GuildExt

logger = logging.getLogger(__name__)

class Event(commands.Cog):
    def __init__(self, bot):
        self.bot:commands.Bot = bot
        self.defaultdb = serverdb.defaultdb
        self.DefaultPrefix = serverdb.defaultdb["prefix"]


# Get prefix in string
    def prefix_str(self, ctx):
        if not ctx.guild:
            return self.DefaultPrefix
        with open(serverdb.SERVER_DATABASE, "r") as jsonfr:
            return json.load(jsonfr)[str(ctx.guild.id)].get("prefix", self.DefaultPrefix)

# Change activity / presence
    @tasks.loop(seconds=60, reconnect=True)
    async def changeBotPresence(self):
        from discord import Streaming, Game, Activity, ActivityType

        presence = [
            Activity(type=ActivityType.listening,
                     name="Music 🎧~ | >>help"),
            # Game(name=f"with {len(self.bot.guilds)} servers | >>help"),
            Activity(type=ActivityType.watching,
                     name="MCW sleeping | >>help"),
            Game(name="Music 🎧 | >>help"),
        ]

        from random import choice as randomChoice
        await self.bot.change_presence(activity=randomChoice(presence))

    # @commands.Cog.listener()
    async def on_message(self,message:discord.Message):
        
        if message.author.bot:
            return
            
        ctx = await self.bot.get_context(message)

        if ctx.valid:
            await ctx.typing()
            await webhook_logger.ctx_log(ctx)
            command = f"{ctx.prefix}{ctx.invoked_with}"
            replaced = ctx.message.content.replace(command,'',1)
            params = f", parameters = [{replaced} ]" if replaced else ''
            logger.info(f"Command \"{ctx.command.name}\" is called{params}.")
            await ctx.bot.invoke(ctx)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        from my_buttons import MusicButtons,CONTROLLER_IDS
        from music import voice_utils


        # Ensures that it is a button
        try:
            if not (interaction.data["component_type"] == 2 and "custom_id" in interaction.data.keys()):
                return 
        except (AttributeError,KeyError): 
            return
        
        custom_id = interaction.data["custom_id"]

        logger.info(f"Button \"{custom_id}\" is pressed.")
        await webhook_logger.interaction_log(interaction)        
        
        guild : GuildExt = interaction.guild
        queue  = guild.song_queue
        message = interaction.message

        #Tons of Buttons
        if custom_id == "delete":
            return await message.delete()

        elif custom_id == "play_again":
            return await MusicButtons.on_play_again_btn_press(interaction,self.bot)

        
        # Clearing glitched messages
        
        if (
            interaction.response.is_done() or # Responsed
            custom_id not in CONTROLLER_IDS # Not audio controller message
        ):
            return

        # at this point we are kinda certain that it is an audio message
        if not guild.voice_client or queue.current_track is None or queue.audio_message.id != message.id:

            logger.warning("Removing unhandled audio message.")
            try:
                await interaction.response.defer()
            except (discord.errors.InteractionResponded,discord.errors.HTTPException):
                pass
            return await voice_utils.clear_audio_message(specific_message=message)

# Setting up

    def guess_the_command(self, wrong_cmd, prefix):

        # Create a command list without admin commands
        clientCmdList = []
        cmd_aliases_list = []
        [clientCmdList.extend(cog.get_commands()) for cog in self.bot.cogs.values(
        ) if 'admin' not in cog.qualified_name]
        for cmd in clientCmdList:
            aliases = cmd.aliases
            aliases.insert(0, cmd.name)
            cmd_aliases_list.append(aliases)

        # Match any possible commands
        matchs = []
        for aliases in cmd_aliases_list:
            for alia in aliases:
                if alia in wrong_cmd or wrong_cmd in alia:
                    matchs.append(alia)
                    break

        # Return the result
        if len(matchs) == 0:
            return f"Type `{prefix}help` if you need some help ! 🙌"
        connector = f" / {prefix}"
        return f"Did you mean `{prefix}{connector.join(matchs)}` 🤔"


# Error handling (reply and logging)

    @commands.Cog.listener()
    async def on_command_error(self, ctx:commands.Context, command_error:commands.errors.CommandError):
        await webhook_logger.event_log(f"{ctx.author} triggered an error : {(command_error.__class__.__name__)}",description = f"in #{ctx.channel} | {ctx.guild}")

        # Invaild command
        if isinstance(command_error, commands.errors.CommandNotFound):
            wrong_cmd = str(command_error)[9:-14]
            await ctx.replywm(ReplyStrings.command_not_found_msg.format(self.guess_the_command(wrong_cmd,ctx.prefix)))

        # Not In Server
        elif isinstance(command_error, commands.errors.NoPrivateMessage):
            await ctx.replywm(ReplyStrings.not_in_server_msg)
        
        # Permissions Errors
        elif isinstance(command_error, commands.errors.NotOwner):
            pass
        elif isinstance(command_error, commands.errors.MissingPermissions):
            await ctx.replywm(ReplyStrings.missing_perms_msg)
        elif isinstance(command_error, commands.errors.BotMissingPermissions):
            await ctx.replywm(ReplyStrings.bot_lack_perm_msg.format(', '.join(command_error.missing_perms)))
        
        elif isinstance(command_error, custom_errors.AudioNotSeekable):
            await ctx.replywm("Audio tracks with 10 mins + duration cannot rewind.")

        # Arguments Errors
        elif isinstance(command_error, commands.errors.MissingRequiredArgument):
            missed_arg = command_error.param
            await ctx.replywm(ReplyStrings.missing_arg_msg.format(missed_arg))
        elif isinstance(command_error, commands.errors.BadBoolArgument):
            await ctx.replywm(ReplyStrings.invaild_bool_msg)

        # Not Found Errors
        elif isinstance(command_error, commands.errors.UserNotFound):
            await ctx.replywm(ReplyStrings.user_not_found_msg)
        elif isinstance(command_error, commands.errors.ChannelNotFound):
            await ctx.replywm(ReplyStrings.channel_not_found_msg)
        elif isinstance(command_error,discord.errors.NotFound):
            pass

        # Voice Errors
        elif isinstance(command_error, custom_errors.UserNotInVoiceChannel):
            await ctx.replywm(ReplyStrings.user_not_in_vc_msg)
        elif isinstance(command_error, custom_errors.NotInVoiceChannel):
            await ctx.replywm(ReplyStrings.bot_not_in_vc_msg)
        elif isinstance(command_error, custom_errors.NoAudioPlaying):
            await ctx.replywm(ReplyStrings.not_playing_msg)

        # Queue Errors
        elif isinstance(command_error, custom_errors.QueueEmpty):
            await ctx.replywm(ReplyStrings.queue_empty_msg)
        elif isinstance(command_error, custom_errors.QueueDisabled):
            await ctx.replywm(ReplyStrings.queue_disabled_msg.format(ctx.prefix))
        
        #Others
        elif isinstance(command_error,commands.errors.CommandInvokeError):
            orginal_error:Exception = command_error.__cause__
            logger.error(f'{orginal_error.__class__.__name__} ouccurs when `>>{ctx.command}` was called : {orginal_error}')
            
            if isinstance(orginal_error,discord.errors.HTTPException) and "404" in str(orginal_error):
                logger.info("Passed 404 not found.")
            else:
                #Code error
                await webhook_logger.error_log(command_error.__cause__)
                raise command_error.__cause__.with_traceback(command_error.__cause__.__traceback__)
        

        #Uknown/ unhandled DISCORD errors
        else:
            logger.error("an error occured",exc_info=command_error)
            await webhook_logger.error_log(command_error)


# Server joining

    @commands.Cog.listener()
    async def on_guild_join(self, guild:discord.Guild):
        link = await guild.system_channel.create_invite(unique=False, max_age=0, max_uses=0)
        await webhook_logger.event_log(f"Joined {guild.name}",url = link)

        # welcome embed
        from discord import Embed
        welcome_embed = Embed(
            title="**🙌🏻 Thanks for inviting me to this server !**",
            description=f"Type {self.DefaultPrefix}command for some instruction !",
        )
        # description = f"This server looks cool! With me, we can make it even better !\nYou are now able to vibe with others in the wave of music 🎶~\n\nyou can already start using the commands ! ( Type {self.DefaultPrefix}help if you need some instructions )")

        # Search for a channel to send the Embed
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                await channel.send(embed=welcome_embed)
                break

        # Settle the database for the server
        with open(serverdb.SERVER_DATABASE, "r+") as jsonf:
            data = json.load(jsonf)

            data[str(guild.id)] = self.defaultdb

            jsonf.seek(0)
            json.dump(data, jsonf, indent=3)


async def setup(bot : commands.Bot):
    await bot.add_cog(Event(bot))