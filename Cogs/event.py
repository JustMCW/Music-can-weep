from discord.ext import commands, tasks
from Response import MessageString
import json
import os
import discord

from log import Logging

DiscordServerDatabase = "Database/DiscordServers.json"
#--------------------#


class event(commands.Cog):
    def __init__(self, bot, info):
        self.bot:commands.Bot = bot
        self.DefaultPrefix = info.DefaultPrefix
        self.DefaultDatabase = info.DefaultDatabase

        self.cmd_aliases_list = []

# make sure every server has a database
    def checkDatabase(self):
        with open(DiscordServerDatabase, "r+") as jsonf:
            data = json.load(jsonf)

            for guild in self.bot.guilds:

                if str(guild.id) not in data.keys():
                    print(guild, "lacking Database")
                    data[str(guild.id)] = self.DefaultDatabase
                elif data[str(guild.id)].keys() != self.DefaultDatabase.keys():
                    data[str(guild.id)] = dict(
                        self.DefaultDatabase, **data[str(guild.id)])
                    print(guild, "has incorrect key")

            jsonf.seek(0)
            json.dump(data, jsonf, indent=3)


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

        print(f"Running as {self.bot.user.name} :")

        self.checkDatabase()

        from discord_components import DiscordComponents
        DiscordComponents(self.bot)

        #Register the custom errors
        import custom_errors

        #Register the song queue on the discord guild object
        from Music.queue import SongQueue
        discord.Guild._song_queue = SongQueue()

        @property
        def song_queue(self:discord.Guild):
            """Represents the song queue of the guild"""
            if self._song_queue is self:
                return self._song_queue
            self._song_queue.guild = self
            return self._song_queue
        discord.Guild.song_queue = song_queue

        #Load the cogs for the bot
        cogs = [pyf.replace(".py", "") for pyf in filter(lambda name: name.endswith(".py"), os.listdir("./Cogs"))]
        
        for cog_name in cogs:
            try:
                self.bot.load_extension(f'Cogs.{cog_name}')
            except commands.errors.NoEntryPointError:
                if cog_name != self.qualified_name:
                    raise
            except commands.errors.ExtensionAlreadyLoaded:
                return
            except commands.errors.ExtensionFailed as ExtFailure:
                print(ExtFailure)
                await self.bot.close()

        #Since we cannot edit it direactly
        self.bot.get_command("help").description = "☁️ Send guides about this bot and it's commands"
        self.bot.get_command("help").usage = "{}help play"

        # Message that tell us we have logged in
        await Logging.log(f"Logged in as {self.bot.user.mention} ( running in {len(self.bot.guilds)} servers ) ;")

        # Start a background task
        self.changeBotPresence.start()

    def guess_the_command(self, wrong_cmd, prefix):

        # Create a command list without admin commands
        clientCmdList = []
        self.cmd_aliases_list = []
        [clientCmdList.extend(cog.get_commands()) for cog in self.bot.cogs.values(
        ) if 'admin' not in cog.qualified_name]
        for cmd in clientCmdList:
            aliases = cmd.aliases
            aliases.insert(0, cmd.name)
            self.cmd_aliases_list.append(aliases)

        # Match any possible commands
        matchs = []
        for aliases in self.cmd_aliases_list:
            for alia in aliases:
                if alia in wrong_cmd or wrong_cmd in alia:
                    matchs.append(alia)
                    break

        # Return the result
        if len(matchs) == 0:
            return f"Type `{prefix}help` if you need some help ! 🙌"
        connector = f" / {prefix}"
        return f"Did you mean `{prefix}{connector.join(matchs)}` 🤔"


# Error handling ( reply and logging)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, commandError):
        commands.errors = commands.errors
        print(commandError)
        await Logging.log(f"{ctx.author} triggered an error : `{(commandError.__class__.__name__)}` in [{ctx.guild}] ;")

        # Invaild command (command not found)
        if isinstance(commandError, commands.errors.CommandNotFound):
            wrong_cmd = str(commandError)[9:-14]
            await ctx.reply(MessageString.command_not_found_msg.format(self.guess_the_command(wrong_cmd, self.prefix_str(ctx))))

        # Not in server / in private message
        elif isinstance(commandError, commands.errors.NoPrivateMessage):
            await ctx.reply(MessageString.not_in_server_msg)

        elif isinstance(commandError, commands.errors.NotOwner):
            print(f"{ctx.author} your not owner lol")

        # User missing permission (not owner / missing some permisson)
        elif isinstance(commandError, commands.errors.MissingPermissions):
            await ctx.reply(MessageString.missing_perms_msg)

        # Bot missing permsion
        elif isinstance(commandError, commands.errors.BotMissingPermissions):
            await ctx.reply(MessageString.bot_lack_perm_msg)

        # User missing command argument
        elif isinstance(commandError, commands.errors.MissingRequiredArgument):
            missed_arg = str(commandError)[:-40]
            await ctx.reply(MessageString.missing_arg_msg.format(missed_arg))

        # Input User not found
        elif isinstance(commandError, commands.errors.UserNotFound):
            await ctx.reply(MessageString.user_not_found_msg)

        # Input Channel not found
        elif isinstance(commandError, commands.errors.ChannelNotFound):
            await ctx.reply(MessageString.channel_not_found_msg)

        # Custom Errors
        if isinstance(commandError, commands.errors.UserNotInVoiceChannel):
            await ctx.reply(MessageString.user_not_in_vc_msg)

        elif isinstance(commandError, commands.errors.NotInVoiceChannel):
            await ctx.reply(MessageString.bot_not_in_vc_msg)
        elif isinstance(commandError, commands.errors.NoAudioPlaying):
            await ctx.reply(MessageString.not_playing_msg)

        elif isinstance(commandError, commands.errors.QueueEmpty):
            await ctx.reply(MessageString.queue_empty_msg)
        elif isinstance(commandError, commands.errors.QueueDisabled):
            await ctx.reply(MessageString.queue_disabled_msg.format(ctx.prefix))

        elif isinstance(commandError, commands.errors.CheckFailure):
            await ctx.reply(MessageString.queue_disabled_msg.format(ctx.prefix))

        elif "NotFound" in str(commandError):
            pass

        # or else it would be the code's error
        else:
            await Logging.error(str(commandError))


# Server joining

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        link = await guild.system_channel.create_invite(xkcd=True, max_age=0, max_uses=0)
        await Logging.log(f"Joined `{guild.name}` ( ID :{guild.id}) <@{self.bot.owner_id}>;{link}")

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
