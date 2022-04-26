#This script is relativly easy , try to figure it out yourself :P

from typing import Any
import discord,json
from discord.ext import commands
from discord_components import Button, ButtonStyle , ActionRow 

from Response import MessageString
from log import Logging
import Convert

DiscordServerDatabase = "Database/DiscordServers.json"

def read_server_databases() -> dict:
    with open(DiscordServerDatabase,"r") as SVDBjson_r:
        return json.load(SVDBjson_r)

def overwrite_server_database(guildId:int,key:str,value:Any) -> dict:
    Data = read_server_databases()
    Data[str(guildId)][key] = value

    with open(DiscordServerDatabase,"w") as SVDBjson_w:
        json.dump(Data,SVDBjson_w,indent = 3)

    return Data

class other_commands(commands.Cog):
    def __init__(self,bot):
        print("HELP commands is ready")
        self.bot = bot

        from time import time as epochTime
        self.lastRestarted = round(epochTime())
        super().__init__()
  
    #status
    @commands.command(aliases=["info","stats"],
                    description="📊 Display the live status of the bot",
                    usage="{}status")
    async def status(self,ctx):
        await Logging.log(f"{ctx.author} just used status command ;")
        statusEmbed = discord.Embed(
          title = "**Current Status of the Bot**"
        ).add_field(name = "Servers",
                    value = len(self.bot.guilds)
        ).add_field(name = "Voice Channel",
                    value = len(self.bot.voice_clients)
        ).add_field(name = "Latency",
                    value = f'{round(self.bot.latency * 1000)}ms'
        ).add_field(name = "Last Restarted",
                    value = f'<t:{self.lastRestarted}>')

        guild = ctx.guild

        if guild:

            with open(DiscordServerDatabase,"r") as jsonf:
                prefix = json.load(jsonf)[str(guild.id)].get("prefix")

            statusEmbed.add_field(name = 'Server Prefix',
                                  value = f'`{prefix}`'
                      ).add_field(name = 'Server Voice Channel',
                                  value = f"`{ctx.voice_client.channel if ctx.voice_client else 'None'}`")
          
        await ctx.reply(embed = statusEmbed)

    @commands.has_guild_permissions(administrator=True)
    @commands.group(aliases = ["configure","config"],
                    description="Configure the setting of the bot in the server, this group of command requires administrator permission",
                    usage="{0}config prefix !\n{0}config queue off")
    async def configuration(self,ctx):
        await Logging.log(f"{ctx.author} just used config command : {ctx.subcommand_passed} in {ctx.guild} ;")
        if ctx.invoked_subcommand is None:
            await ctx.reply(embed=discord.Embed(
                title = "Configuration command usage : ",
                description = "\n".join([f"{ctx.prefix}{cmd.name} [{'] ['.join(list(cmd.clean_params))}]" for cmd in ctx.command.walk_commands() ]),
                color = discord.Color.from_rgb(255,255,255)
              )  
            )

    #Change prefix in a server
    @configuration.command(aliases = ["prfx",],
                            description = "⚙️ change my command prefix to whatever you want , maximum 5 characters",
                            usage="{0}config prefix ?")
    async def prefix(self,ctx,new_prefix):
        

        if len(new_prefix) > 5: 
            return await ctx.reply("🚫 Prefix cannot be longer than 5 characters")
        
        overwrite_server_database(ctx.guild.id,
                                  key="prefix",
                                  value=new_prefix)

        await ctx.reply(f"**✅ Successfully changed prefix to `{new_prefix}`**")

    @configuration.command(aliases = ["queue"],
                            description="Enable / Disable queuing songs in the server",
                            usage="{}config queue off")
    async def queuing(self,ctx,mode):
        mode:bool = Convert.str_to_bool(mode)

        if mode is None:
            return await ctx.reply(MessageString.invaild_mode_msg)

        if mode == False and len(ctx.guild.song_queue) != 0 :
            return await ctx.reply(f"There are still tracks remaining in the queue, it must be empty. ( `{ctx.prefix}queue clear` will clear it for you )")

        overwrite_server_database(ctx.guild.id,
                                  key="queuing",
                                  value=mode)
        await ctx.reply("Song tracks will now queue up when being request" if mode else "Song tracks will now be instantly played when request ")

def setup(BOT):
    BOT.add_cog(other_commands(BOT))