#This script is relativly easy , try to figure it out yourself :P

from typing import Any
import discord
from discord.ext import commands
import logging
from discord_components import Button, ButtonStyle , ActionRow 

from Database import Management

class OtherCommands(commands.Cog):
    def __init__(self,bot):
        logging.info("HELP commands is ready")
        self.bot = bot

        from time import time as epochTime
        self.lastRestarted = round(epochTime())
        super().__init__()
  
    #status
    @commands.command(aliases=["info","stats"],
                    description="📊 Display the live status of the bot",
                    usage="{}status")
    async def status(self,ctx):
        

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



        try:
            status_embed.add_field(name = 'Server Prefix',
                                  value = f'`{ctx.guild.database.get("prefix")}`'
                      ).add_field(name = 'Server Voice Channel',
                                  value = f"`{ctx.voice_client.channel if ctx.voice_client else 'None'}`")
        except AttributeError: 
            pass
        finally:
            await ctx.reply(embed = status_embed)

    @commands.has_guild_permissions(administrator=True)
    @commands.group(aliases = ["configure","config"],
                    description="Configure the setting of the bot in the server, this group of command requires administrator permission",
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
    @configuration.command(aliases = ["prfx",],
                            description = "⚙️ change my command prefix to whatever you want , maximum 5 characters",
                            usage="{0}config prefix !")
    async def prefix(self,ctx,new_prefix):
        

        if len(new_prefix) > 5: 
            return await ctx.reply("🚫 Prefix cannot be longer than 5 characters")
        
        Management.overwrite_server_database(ctx.guild,
                                            key="prefix",
                                            value=new_prefix)

        await ctx.reply(f"**✅ Successfully changed prefix to `{new_prefix}`**")

    @configuration.command(aliases = ["queue","q"],
                            description="Enable / Disable queuing songs in the server",
                            usage="{}config queue off")
    async def queuing(self,ctx,mode):
        mode:bool = commands.core._convert_to_bool(mode)

        if mode == False and ctx.guild.song_queue:
            return await ctx.reply(f"There are still tracks remaining in the queue, it must be empty to perform this command. ( `{ctx.prefix}queue clear` will clear it for you )")

        Management.overwrite_server_database(ctx.guild,
                                            key="queuing",
                                            value=mode)
        await ctx.reply("Song tracks will now queue up when being requested" if mode else "Song tracks will now be instantly played when requested")

def setup(BOT):
    BOT.add_cog(OtherCommands(BOT))