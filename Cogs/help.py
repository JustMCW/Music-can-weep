#This script is relativly easy , try to figure it out yourself :P

from typing import Any
import discord,json
from discord.ext import commands
from discord_components import Button, ButtonStyle , ActionRow 

from replies import Replies
from log import Logging
from convert import Convert

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

class support_commands(commands.Cog):
    def __init__(self,bot):
        print("HELP commands is ready")
        self.bot = bot

        from time import time as epochTime
        self.lastRestarted = round(epochTime())
        super().__init__()

    #guide   
    @commands.command(aliases = ["how","setup","h"],description = "👍🏻 Send a message to teach you how to use me")
    async def help(self,ctx):
      
        await Logging.log(f"{ctx.author} just used help command")

        if ctx.guild: 
            await ctx.reply("🙂 I have a lot to tell you, so let's talk in DM !")

        owner = await self.bot.fetch_user(self.bot.owner_id)

        botDescription = (
          "**👋 Greeting ! Glad that you are reading this , highly appreciated !**"+
          '\n'+
          "\nBy inviting me to your server , you will be able to play music and vibe with your friends ! 🎶 I also offers a cool and useful **BUTTON FEATURE **⏸ ▶ "+
          "\nso you don't have to type to interact with the audio!" +
          '\n'+
          "\nTo start up with , invite me to your discord server !"+
          "\nTap the Button below to invite me 🔗 "
          f"\nWhat can i do ? Simply type `{ctx.prefix}cmd` or tap the button below for a list of commands !"+
          '\n'
          f"\n**Lastly , if you need further more help or faced bugs / glitches , contact {owner.mention} / {owner}**"
        )

        import datetime
        help_embed = discord.Embed(title = "**All about Music Can Weep**",
                                  description = botDescription,
                                  color = discord.Color.from_rgb(255,255,255),
                                  timestamp=datetime.datetime.now()
                  ).set_thumbnail(url = self.bot.user.avatar_url)

        cmdListBtn = Button(label = "show me the command list",
                            style = ButtonStyle.blue,
                            custom_id = "cmd",
                            emoji = "📄")

        invBtn = Button(label = "invite me to your server !",
                        style = ButtonStyle.URL,
                        url = "https://discord.com/api/oauth2/authorize?client_id=919597280523345961&permissions=274881170944&scope=bot",
                        emoji = "🔗")

        DM = await ctx.author.create_dm()
        help_msg = await DM.send(embed = help_embed,
                                 components = ActionRow([cmdListBtn,invBtn]))
        try:
            btn = await self.bot.wait_for(event="button_click",
                                          timeout = 60 , 
                                          check = lambda btn: btn.message.id == help_msg.id)
        except:
            await help_msg.edit(components = [invBtn])
        else: 
            await btn.edit_origin(components = [invBtn])
            await self.command(ctx)
        
    #show all commands
    @commands.command(aliases = ["cmd","cmds","commandlist"],description = "🗒 Display this message")
    async def command(self,ctx):
        await Logging.log(f"{ctx.author} viewed the command list")
        final_list = f"**👍🏻 Few things to know before continue reading :**\
          \n\n✅ *[argument] means it's required and <argument> means it's optional*\
          \n✅ *You can mention {self.bot.user.mention} instead of a typing a prefix*"

        cogs = self.bot.cogs

        for cog_name in cogs:
            if "admin" in cog_name in cog_name.lower():  
                continue
              
            final_list += f"\n\n**{cog_name.replace('_',' ').upper()}**\n"
            
            for command in cogs[cog_name].get_commands():
                name = command.name

                params = list(command.params.values())

                true_params = []
                for parm in params:
                    parm = str(parm)
                    if parm == "self" or parm == "ctx" or "kwar" in parm: 
                        continue
                    if "=None" in parm: 
                        true_params.append(f"<{parm.replace('=None','')}>")
                    else: 
                        true_params.append(f"[{parm}]")

                desc = f"```coffee\n{command.description}```"
                final_list += f"\n`{ctx.prefix}{name} {''.join(true_params)}`\n{desc}"
                
                #Subcommands
                try:
                    for sub_command in command.walk_commands():
                        name = sub_command.name

                        params = list(sub_command.params.values())

                        true_params = []
                        for parm in params:
                            parm = str(parm)
                            if parm == "self" or parm == "ctx" or "kwar" in parm: 
                                continue
                            if "=None" in parm: 
                                true_params.append(f"<{parm.replace('=None','')}>")
                            else: 
                                true_params.append(f"[{parm}]")

                        desc = f"```coffee\n{sub_command.description}```"
                        final_list += f"\n`{ctx.prefix} {command.name} {name} {''.join(true_params)}`\n{desc}"
                except AttributeError:
                    continue

        DM = await ctx.author.create_dm()
        await DM.send(embed = discord.Embed(title = "Available commands for Music Can Weep",
                      description = final_list,
                      color = discord.Color.from_rgb(255,255,255)))
    
    #status
    @commands.command(aliases=["info","stats"],description="📊 Display the live status of the bot")
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
    @commands.group(aliases = ["configure","configuration","serverconfig","server_config"],
                    description="Configure the setting of the bot in the server, this group of command requires administrator permission")
    async def config(self,ctx):
        await Logging.log(f"{ctx.author} just used config command : {ctx.subcommand_passed} in {ctx.guild} ;")
        if ctx.invoked_subcommand is None:
            await ctx.reply(embed=discord.Embed(
                title = "Configuration command usage : ",
                description = "\n".join([f"{ctx.prefix}{cmd.name} [{'] ['.join(list(cmd.clean_params))}]" for cmd in ctx.command.walk_commands() ]),
                color = discord.Color.from_rgb(255,255,255)
              )  
            )

    #Change prefix in a server
    @config.command(aliases = ["newprefix","change_prefix_to","sp","setprefix"],
                    description = "⚙️ change my command prefix to whatever you want , maximum 5 characters")
    async def prefix(self,ctx,new_prefix):
        

        if len(new_prefix) > 5: 
            return await ctx.reply("🚫 Prefix cannot be longer than 5 characters")
        
        overwrite_server_database(ctx.guild.id,
                                  key="prefix",
                                  value=new_prefix)

        await ctx.reply(f"**✅ Successfully changed prefix to `{new_prefix}`**")

    @config.command(aliases = ["queue"],
                    description="Enable / Disable queuing songs in the server")
    async def queuing(self,ctx,mode):
        mode:bool = Convert.str_to_bool(mode)

        if mode is None:
            return await ctx.reply(Replies.invaild_mode_msg)

        if mode == False and len(self.bot.cogs["music_commands"].get_queue(ctx.guild)) != 0 :
            return await ctx.reply(f"There are still tracks remaining in the queue, it must be empty. ( `{ctx.prefix}queue clear` will clear it for you )")

        overwrite_server_database(ctx.guild.id,
                                  key="queuing",
                                  value=mode)
        await ctx.reply("Song tracks will now queue up when being request" if mode else "Song tracks will now be instantly played when request ")

def setup(BOT):
    BOT.add_cog(support_commands(BOT))