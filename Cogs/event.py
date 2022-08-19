import json
import os
import logging
import discord
from discord.ext import commands, tasks
from Response    import MessageString
from Database import Management


DiscordServerDatabase = "Database/DiscordServers.json"
#--------------------#


class Event(commands.Cog):
    def __init__(self, bot, info):
        self.bot:commands.Bot = bot
        self.DefaultDatabase = info.DefaultDatabase
        self.DefaultPrefix = info.DefaultDatabase["prefix"]


# Get prefix in string
    def prefix_str(self, ctx):
        if not ctx.guild:
            return self.DefaultPrefix
        with open(DiscordServerDatabase, "r") as jsonfr:
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

# Setting up
    @commands.Cog.listener()
    async def on_ready(self):

        logging.warning(f"Running as {self.bot.user.name} :")

        from discord_components import DiscordComponents
        DiscordComponents(self.bot)

        #Register the custom errors
        import custom_errors

        #Register the song queue and database on the discord guild object
        from Music.song_queue import SongQueue
        import discord

        #Init 
        Management.initialize(self.bot)

        @property
        def song_queue(self) -> SongQueue:
            """
            Represents the song queue of the guild
            """
            return SongQueue.get_song_queue_for(self)
            
        discord.Guild.song_queue=song_queue

        @property
        async def database(self) -> dict:
            """
            Represents the database which is from `Database.DiscordServers.json` of the guild 
            """
            return await Management.read_database_of(self)
        discord.Guild.database=database
        
        #Load the cogs for the bot
        cogs = [pyf.replace(".py", "") for pyf in filter(lambda name: name.endswith(".py"), os.listdir("./Cogs"))]
        
        for cog_name in cogs:
            try:
                self.bot.load_extension(f'Cogs.{cog_name}')
            except commands.errors.NoEntryPointError:
                if cog_name != self.qualified_name.lower():
                    raise
            except commands.errors.ExtensionAlreadyLoaded:
                return
            except commands.errors.ExtensionFailed as ExtFailure:
                logging.error(ExtFailure)
                await self.bot.close()
                raise ExtFailure.__cause__.with_traceback(ExtFailure.__cause__.__traceback__)

        #Since we cannot edit it direactly
        self.bot.get_command("help").description = "☁️ Send guides about this bot and it's commands"
        self.bot.get_command("help").usage = "{}help play"

        # Message that tell us we have logged in
        logging.webhook_log_event(f"Logged in as {self.bot.user.name} ( running in {len(self.bot.guilds)} servers ) ;",thumbnail = self.bot.user.avatar_url)

        await Management.check_server_database(self.bot)

        # Start a background task  
        self.changeBotPresence.start()

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
        logging.webhook_log_event(f"{ctx.author} triggered an error : {(command_error.__class__.__name__)}",description = f"in #{ctx.channel} | {ctx.guild}")

        # Invaild command
        if isinstance(command_error, commands.errors.CommandNotFound):
            wrong_cmd = str(command_error)[9:-14]
            await ctx.reply(MessageString.command_not_found_msg.format(self.guess_the_command(wrong_cmd,ctx.prefix)))

        # Not In Server
        elif isinstance(command_error, commands.errors.NoPrivateMessage):
            await ctx.reply(MessageString.not_in_server_msg)
        
        # Permissions Errors
        elif isinstance(command_error, commands.errors.NotOwner):
            pass
        elif isinstance(command_error, commands.errors.MissingPermissions):
            await ctx.reply(MessageString.missing_perms_msg)
        elif isinstance(command_error, commands.errors.BotMissingPermissions):
            await ctx.reply(MessageString.bot_lack_perm_msg.format(', '.join(command_error.missing_perms)))

        # Arguments Errors
        elif isinstance(command_error, commands.errors.MissingRequiredArgument):
            missed_arg = str(command_error)[:-40]
            await ctx.reply(MessageString.missing_arg_msg.format(missed_arg))
        elif isinstance(command_error, commands.errors.BadBoolArgument):
            await ctx.reply(MessageString.invaild_bool_msg)

        # Not Found Errors
        elif isinstance(command_error, commands.errors.UserNotFound):
            await ctx.reply(MessageString.user_not_found_msg)
        elif isinstance(command_error, commands.errors.ChannelNotFound):
            await ctx.reply(MessageString.channel_not_found_msg)
        elif isinstance(command_error,discord.errors.NotFound):
            pass

        # Voice Errors
        elif isinstance(command_error, commands.errors.UserNotInVoiceChannel):
            await ctx.reply(MessageString.user_not_in_vc_msg)
        elif isinstance(command_error, commands.errors.NotInVoiceChannel):
            await ctx.reply(MessageString.bot_not_in_vc_msg)
        elif isinstance(command_error, commands.errors.NoAudioPlaying):
            await ctx.reply(MessageString.not_playing_msg)

        # Queue Errors
        elif isinstance(command_error, commands.errors.QueueEmpty):
            await ctx.reply(MessageString.queue_empty_msg)
        elif isinstance(command_error, commands.errors.QueueDisabled):
            await ctx.reply(MessageString.queue_disabled_msg.format(ctx.prefix))
        
        #Others
        elif isinstance(command_error,commands.errors.CommandInvokeError):
            orginal_error:Exception = command_error.__cause__
            logging.error(f'{orginal_error.__class__.__name__} ouccurs when `>>{ctx.command}` was called : {orginal_error}')
            
            if isinstance(orginal_error,discord.errors.HTTPException) and "404" in str(orginal_error):
                logging.info("Passed 404 not found.")
            else:
                #Code error
                logging.webhook_log_error(command_error.__cause__)
                raise command_error.__cause__.with_traceback(command_error.__cause__.__traceback__)
        

        #Uknown/ unhandled DISCORD errors
        else:
            logging.webhook_log_error(command_error)


# Server joining

    @commands.Cog.listener()
    async def on_guild_join(self, guild:discord.Guild):
        link = await guild.system_channel.create_invite(xkcd=True, max_age=0, max_uses=0)
        logging.webhook_log_event(f"Joined {guild.name}",url = link)

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
        with open(DiscordServerDatabase, "r+") as jsonf:
            data = json.load(jsonf)

            data[str(guild.id)] = self.DefaultDatabase

            jsonf.seek(0)
            json.dump(data, jsonf, indent=3)
