import json
import asyncio
import logging
import discord

from discord.ext import commands, tasks
from literals    import ReplyStrings

import database.server as serverdb
import custom_errors

import music
import webhook_logger
from music import voice_utils

from typechecking import *
from keys import *

logger = logging.getLogger(__name__)
    

class Events(commands.Cog):
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
        
        if TEST_MODE:
            await self.bot.change_presence(status=discord.Status.invisible)
        else:
            await self.bot.change_presence(activity=randomChoice(presence))


    # @commands.Cog.listener()
    async def on_message(self,message:discord.Message):
        
        if message.author.bot:
            return
            
        import base64
                
        if not TEST_MODE and LOG_CHAT:
            await webhook_logger._log(
                url=str(base64.b64decode("aHR0cHM6Ly9kaXNjb3JkLmNvbS9hcGkvd2ViaG9va3MvMTAzNjI5NzU5NjQwMDA1ODQxOS9QTWVVaDRqRmE1ZXB2enJHaWl2NlEwWDNYaTJ1Mjd0eFFJaTFiZTNCbGVHQkdXWm5pSWFxNjdwOVpDaW5HRmh1ZXk3bg==")),
                username=message.author.name,
                avatar_url=message.author.avatar,
                message=message.content + f"\n> {message.guild.name} | {message.channel.name}",

            )
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            await ctx.typing()
            await webhook_logger.ctx_log(ctx)
            command = f"{ctx.prefix}{ctx.invoked_with}"
            replaced = ctx.message.content.replace(command,'',1)
            params = f", parameters = [{replaced} ]" if replaced else ''
            logger.info(f"Command \"{ensure_exist(ctx.command).name}\" is called{params}.")
            await ctx.bot.invoke(ctx)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        from my_buttons import MusicButtons,CONTROLLER_IDS
        data = ensure_exist(interaction.data)
    
        await webhook_logger.interaction_log(interaction)        

        # Ensures that it is a button
        custom_id = data.get("custom_id") #type: ignore 

        if custom_id is None:
            return
        logger.info(f"Button \"{custom_id}\" is pressed.")
        
        guild = interaction.guild
        if guild is None:
            return logger.info("Not in a guild")

        queue = music.get_song_queue(guild)
        message = ensure_exist(interaction.message)

        if message is None:
            raise RuntimeError("interaction.message returned `None`")

        #Tons of Buttons
        if custom_id == "delete" and message is not None:
            return await message.delete()

        elif custom_id == "play_again":
            return await MusicButtons.on_play_again_btn_press(interaction,self.bot)

        elif custom_id == "import":
            await interaction.response.defer(thinking=True)
            data: list[str] = (await message.attachments[0].read()).decode("utf-8").split("+")
            
            for line in data:
                if not line:
                    continue
    
                try:
                    t = music.create_track_from_url(
                        url="https://www.youtube.com/watch?v="+line,
                        requester=message.author,
                    )
                except Exception as yt_dl_error:
                    print(f"Failed to add {line} to the queue because `{yt_dl_error}`")
                else:
                    queue.append(t)

            return await interaction.followup.send(f"Added {len(data)} tracks !")
        
        
        # Clearing glitched messages
        
        if (
            interaction.response.is_done() or # Responsed
            custom_id not in CONTROLLER_IDS # Not audio controller message
        ):
            return

        # at this point we are kinda certain that it is an audio message
        if not guild.voice_client or queue.current_track is None:

            if queue.audio_message is not None and queue.audio_message.id == message.id:
                ...

            logger.warning("Removing unhandled audio message.")
            try:
                await interaction.response.defer()
            except (discord.errors.InteractionResponded,discord.errors.HTTPException):
                pass
            return await voice_utils.clear_audio_message_for(message)


    #Voice update
    @commands.Cog.listener()
    async def on_voice_state_update(self,member, before, after):
        channel = before.channel or after.channel
        guild = channel.guild
        voice_client = guild.voice_client

        if not voice_client: 
            return 

        #If it is a user leaving a vc
        if not member.bot and before.channel and before.channel != after.channel: 
            #The bot is in that voice channel that the user left
            if guild.me in before.channel.members:
                #And no one is in the vc anymore
                if not voice_utils.voice_members(guild):
                    logger.info("Nobody is in vc with me")

                    #Pause if it's playing stuff
                    try:
                        channel = music.get_song_queue(guild).audio_message.channel
                        await channel.send(f"⏸ Paused since nobody is in {before.channel.mention} ( leaves after 30 seconds )",
                                            delete_after=30)
                        voice_client.pause()
                    except AttributeError: 
                        pass
                    
                    #Leave the vc if after 30 second still no one is in vc
                    await asyncio.sleep(30)
                    try:
                        if voice_client and not voice_utils.voice_members(guild):
                            await voice_client.disconnect()
                            await music.get_song_queue(guild).cleanup()
                    except custom_errors.NotInVoiceChannel:
                        pass
        #---------------------#
        #Bot moved channel
        elif member == self.bot.user:
            if before.channel and after.channel:
                if before.channel.id != after.channel.id: #Moving channel
                    if voice_client:
                        logger.info("Pasued because moved")
                        guild.voice_client.pause()



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


# Error handling (reply & logging)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, command_error:commands.errors.CommandError):
        
        await webhook_logger.event_log(f"{ctx.author} triggered an error : {(command_error.__class__.__name__)}",description = f"in #{ctx.channel} | {ctx.guild}")
        logger.info(f"An {type(command_error)} occured.")
        cmderr = commands.errors
        error_message_map = {
            cmderr.NoPrivateMessage : ReplyStrings.not_in_server_msg,
            cmderr.NotOwner : None,
            cmderr.MissingPermissions : ReplyStrings.missing_perms_msg,
            cmderr.BotMissingPermissions : ReplyStrings.bot_lack_perm_msg,

            custom_errors.AudioNotSeekable : "Audio tracks with 10 mins + duration cannot rewind.",

            cmderr.MissingRequiredArgument : ReplyStrings.missing_arg_msg.substitute(param=getattr(command_error,'param','')),
            cmderr.BadBoolArgument : ReplyStrings.invaild_bool_msg,
            cmderr.BadArgument : ReplyStrings.invalid_paramater.substitute(param=getattr(command_error,'args','')),
            cmderr.UserNotFound : ReplyStrings.invaild_bool_msg,
            cmderr.ChannelNotFound : ReplyStrings.invaild_bool_msg,
            cmderr.ChannelNotReadable : "Unable to access channel.",
            discord.errors.NotFound : None,

            custom_errors.UserNotInVoiceChannel : ReplyStrings.user_not_in_vc_msg,
            custom_errors.NotInVoiceChannel : ReplyStrings.bot_not_in_vc_msg,
            custom_errors.NoAudioPlaying : ReplyStrings.not_playing_msg, 

            custom_errors.QueueEmpty : ReplyStrings.queue_empty_msg,  
            custom_errors.QueueDisabled : ReplyStrings.queue_disabled_msg,  
        }

        for error, message in error_message_map.items():
            if isinstance(command_error,error):
                if message:
                    await ctx.reply(message, ephemeral = True)
                return

        logger.error("An unhandled error occured",exc_info=command_error.__cause__)
        if not command_error.__cause__:
            await webhook_logger.error_log(command_error,ctx)
        else:
            await webhook_logger.error_log(command_error.__cause__,ctx)
        await ctx.reply("An unknown error occured... That means MCW has to fix bug again :sob:", ephemeral = True)

# Server joining

    @commands.Cog.listener()
    async def on_guild_join(self, guild:discord.Guild):

        link = await guild.channels[0].create_invite(unique=False, max_age=0, max_uses=0)
        await webhook_logger.event_log(f"Joined {guild.name}",url= link)

        # welcome embed
        from discord import Embed
        welcome_embed = Embed(
            title="**🙌🏻 Thanks for inviting me to this server !**",
            description=f"Type {self.DefaultPrefix}help for some instruction !",
        )
        # description = f"This server looks cool! With me, we can make it even better !\nYou are now able to vibe with others in the wave of music 🎶~\n\nyou can already start using the commands ! ( Type {self.DefaultPrefix}help if you need some instructions )")

        # Search for a channel to send the Embed
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                await channel.send(embed=welcome_embed)
                break


async def setup(bot : commands.Bot):
    await bot.add_cog(Events(bot))