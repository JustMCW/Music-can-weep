#This script is relativly easy , try to figure it out yourself :P

import logging

import discord
from discord.ext import commands

import music
import database.server as serverdb

logger = logging.getLogger(__name__)

class OtherCommands(commands.Cog):
    def __init__(self,bot):
        self.bot = bot

        from time import time as epochTime
        self.lastRestarted = round(epochTime())
        super().__init__()
  
    #status
    @commands.hybrid_command(
        aliases=["info","stats"],
        description="📊 Display the live status of the bot",
        usage="{}status"
    )
    async def status(self,ctx: commands.Context):
        

        status_embed = discord.Embed(
          title = "**Current Status of the Bot**"
        ).add_field(name = "Servers",
                    value = len(self.bot.guilds)
        ).add_field(name = "Voice Channel",
                    value = len(self.bot.voice_clients)
        ).add_field(name = "Latency",
                    value = f'{round(self.bot.latency * 1000)}ms'
        ).add_field(name = "Last Restarted",
                    value = f'<t:{self.lastRestarted}>')



        if ctx.guild:
            status_embed.add_field(
                name = 'Server Prefix',
                value = f'`{serverdb.read_database_of(ctx.guild)["prefix"]}`'
            ).add_field(
                name = 'Server Voice Channel',
                value = f"`{ctx.voice_client.channel if ctx.voice_client else 'None'}`"
            )
       
        await ctx.reply(embed = status_embed)

    @commands.guild_only()
    @commands.hybrid_group(aliases = ["configure","config"],
                    description="Configure the setting of the bot in this server, requires administrator permission",
                    usage="{0}config prefix !\n{0}config queue off")
    async def configuration(self,ctx):
        if ctx.invoked_subcommand is None:
            await ctx.reply(embed=discord.Embed(
                title = "Configuration command usage : ",
                description = "\n".join([f"{ctx.prefix}{cmd.qualified_name} [{'] ['.join(list(cmd.clean_params))}]" for cmd in ctx.command.walk_commands() ]),
                color = discord.Color.from_rgb(255,255,255)
              )  
            )

    #Change prefix in a server
    @configuration.command(
        aliases = ["prfx",],
        description = "⚙️ change my command prefix to whatever you want , maximum 5 characters",
        usage="{0}config prefix !"
    )
    async def prefix(self,ctx, new_prefix: str):
        

        if len(new_prefix) > 5: 
            return await ctx.reply("🚫 Prefix cannot be longer than 5 characters")
        
        serverdb.overwrite_server_database(ctx.guild,
                                            key="prefix",
                                            value=new_prefix)

        await ctx.reply(f"**✅ Successfully changed prefix to `{new_prefix}`**")

    @configuration.command(
        aliases = ["queue","q"],
        description="Enable / Disable queuing songs in the server",
        usage="{}config queue off"
    )
    async def queuing(self,ctx, mode: bool):

        if mode == False and music.get_song_queue(ctx.guild):
            return await ctx.reply(f"There are still tracks remaining in the queue, it must be cleared to perform this command. ( `{ctx.prefix}queue clear` will clear it for you )")

        serverdb.overwrite_server_database(ctx.guild,
                                            key="queuing",
                                            value=mode)
        await ctx.reply("Song tracks will now queue up when being requested" if mode else "Song tracks will now be instantly played when requested")

    @configuration.command(aliases = ["autoclear",],
                            description = "⚙️ clear the queue after leaving the voice channel",
                            usage="{0}config prefix !")
    async def auto_clear_queue(self,ctx, mode : bool):
        serverdb.overwrite_server_database(ctx.guild,
                                            key="autoclearing",
                                            value=mode)

        await ctx.reply(f"**✅ Successfully changed auto clearing to `{mode}`**")

async def setup(BOT):
    await BOT.add_cog(OtherCommands(BOT))