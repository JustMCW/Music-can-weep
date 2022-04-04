from discord.ext import commands,tasks
from replies import Replies
import json

from log import Logging
DiscordServerDatabase = "Database/DiscordServers.json"
#--------------------#

class events(commands.Cog,Replies):
  def __init__(self,bot,info):
    self.BOT = bot
    self.DefaultPrefix = info.DefaultPrefix
    self.DefaultDatabase = info.DefaultDatabase

    self.cmd_aliases_list = []

#make sure every server has a database
  def checkDatabase(self):
    with open(DiscordServerDatabase,"r+") as jsonf:
      data = json.load(jsonf)

      for guild in self.BOT.guilds:
        if str(guild.id) not in data.keys():
          print(guild,"lacking Database")
          data[str(guild.id)] = self.DefaultDatabase
        elif data[str(guild.id)].keys() != self.DefaultDatabase.keys():
          data[str(guild.id)] = dict(self.DefaultDatabase , **data[guild.id])
          print(guild,"has incorrect key")
      
      jsonf.seek(0)
      json.dump(data,jsonf,indent = 3)
    

#Get prefix in string
  def prefix_str(self,ctx):
    if not ctx.guild: return self.DefaultPrefix
    with open(DiscordServerDatabase,"r") as jsonfr:
      return json.load(jsonfr)[str(ctx.guild.id)].get("prefix", self.DefaultPrefix)

#Change activity / presence
  @tasks.loop(seconds=60,reconnect=True)
  async def changeBotPresence(self):
    from discord import Streaming,Game,Activity,ActivityType
    from random import choice as randomChoice

    presence = [
      Activity(type=ActivityType.listening, 
              name="Music 🎧~ | >>help"),
      # Game(name=f"with {len(self.BOT.guilds)} servers | >>help"),
      Activity(type=ActivityType.watching,
              name="MCW sleeping | >>help"),
      Game(name="Music 🎧 | >>help"),
    ]

    await self.BOT.change_presence(activity=randomChoice(presence))
#Setting up
  @commands.Cog.listener()
  async def on_ready(self):
    from os import system
    system("clear")
    
    print(f"Running as {self.BOT.user.name} :")

    self.checkDatabase()
    
    from discord_components import DiscordComponents
    DiscordComponents(self.BOT)

    cogs =["bot_admin","help","music"]
    for cog_name in cogs:
      print(f"Loading {cog_name}")
      self.BOT.load_extension(f'Cogs.{cog_name}')

    #Message that tell us we have logged in
    await Logging.log(f"Logged in as {self.BOT.user.mention} ( running in {len(self.BOT.guilds)} servers ) ;")

    #Start a loop
    self.changeBotPresence.start()


  def guess_the_command(self,wrong_cmd,prefix):

    #Create a command list without admin commands
    clientCmdList = []
    self.cmd_aliases_list=[]
    [clientCmdList.extend(cog.get_commands()) for cog in self.BOT.cogs.values() if 'admin' not in cog.qualified_name]
    for cmd in clientCmdList:
      aliases = cmd.aliases
      aliases.insert(0,cmd.name)
      self.cmd_aliases_list.append(aliases)

    #Match any possible commands
    matchs =[]
    for aliases in self.cmd_aliases_list:
      for alia in aliases:
        if alia in wrong_cmd or wrong_cmd in alia:
          matchs.append(alia)
          break

    #Return the result
    if len(matchs) == 0:
      return f"Type `{prefix}help` if you need some help ! 🙌"
    connector = f" / {prefix}"
    return f"Did you mean `{prefix}{connector.join(matchs)}` 🤔"



#Error handling ( reply and logging)
  @commands.Cog.listener()
  async def on_command_error(self,ctx,commandError):
    discord_error = commands.errors
    print(commandError)
    await Logging.log(f"{ctx.author} triggered an error : `{str(commandError)}` in [{ctx.guild}] ;")

    #Invaild command (command not found)
    if isinstance(commandError,discord_error.CommandNotFound):
      wrong_cmd = str(commandError)[9:-14]
      await ctx.reply(super().command_not_found_msg.format(self.guess_the_command(wrong_cmd,self.prefix_str(ctx))))

    #Not in server / in private message
    elif isinstance(commandError,discord_error.NoPrivateMessage):
      await ctx.reply(super().not_in_server_msg)

    elif isinstance(commandError,discord_error.NotOwner):
      print(f"{ctx.author} your not owner lol")

    #User missing permission (not owner / missing some permisson)
    elif isinstance(commandError,discord_error.MissingPermissions):
      await ctx.reply(super().missing_perms_msg)

    #Bot missing permsion
    elif isinstance(commandError,discord_error.BotMissingPermissions):
      await ctx.reply(super().bot_lack_perm_msg)

    #User missing command argument
    elif isinstance(commandError,discord_error.MissingRequiredArgument):
      missed_arg = str(commandError)[:-40]
      await ctx.reply(super().missing_arg_msg.format(missed_arg))

    #Input User not found
    elif isinstance(commandError,discord_error.UserNotFound):
      await ctx.reply(super().user_not_found_msg)

    #Input Channel not found
    elif isinstance(commandError,discord_error.ChannelNotFound):
      await ctx.reply(super().channel_not_found_msg)

    #Custom Errors
    elif isinstance(commandError,discord_error.CommandInvokeError):
      customErrorName = str(commandError)[29:-2]
      if "UserNotInVoiceChannel" == customErrorName: 
        await ctx.reply(super().user_not_in_vc_msg)
      elif "NotInVoiceChannel" == customErrorName: 
        await ctx.reply(super().bot_not_in_vc_msg)
      elif "NoAudioPlaying" == customErrorName: 
        await ctx.reply(super().not_playing_msg)
      elif "BotMissingPermission" == customErrorName: 
        await ctx.reply(super().bot_lack_perm_msg)
      elif "QueueEmpty" == customErrorName: 
        await ctx.reply(super().queue_empty_msg)
      elif "QueueDisabled" == customErrorName:
        await ctx.reply(super().queue_disabled_msg.format(ctx.prefix))
      else:
        await Logging.error(str(commandError))
    
    elif "NotFound" in str(commandError):
      pass
      
    #or else it would be the code's error
    else:
      await Logging.error(str(commandError))
    

#Server joining
  @commands.Cog.listener()
  async def on_guild_join(self,guild):
    link = await guild.system_channel.create_invite(xkcd=True, max_age = 0, max_uses = 0)
    await Logging.log(f"Joined `{guild.name}` ( ID :{guild.id}) <@{self.BOT.owner_id}>;{link}")

    #welcome embed
    from discord import Embed
    welcome_embed = Embed(
      title = "**🙌🏻 Thanks for inviting me to this server !**",
      description = f"Type {self.DefaultPrefix}command for some instruction !",
    )
      # description = f"This server looks cool! With me, we can make it even better !\nYou are now able to vibe with others in the wave of music 🎶~\n\nyou can already start using the commands ! ( Type {self.DefaultPrefix}help if you need some instructions )")

    #Search for a channel to send the Embed
    for channel in guild.text_channels:
      if channel.permissions_for(guild.me).send_messages:
        await channel.send(embed=welcome_embed)
        break

    #Settle the database for the server
    with open(DiscordServerDatabase,"r+") as jsonf:
      data = json.load(jsonf)
      
      data[str(guild.id)] = self.DefaultDatabase
  
      jsonf.seek(0)
      json.dump(data,jsonf,indent = 3)