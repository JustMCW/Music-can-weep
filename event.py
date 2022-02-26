from datetime import datetime as dt
from discord.ext import commands,tasks
from replit import db
from replies import Replies

#--------------------#

is_down = False

class events(commands.Cog,Replies):
  def __init__(self,bot,info):
    self.BOT = bot
    self.default_prefix = info.default_prefix
    self.default_database = info.default_database
    self.log_id = info.cmd_log_id
    self.error_log_id = info.error_log_id
    self.cmd_aliases_list = []

#make sure every server has a database
  def checkDatabase(self):
    for guild in self.BOT.guilds:
      if str(guild.id) not in db.keys():
        print(guild," lacking Database lol")
        db.set(str(guild.id),self.default_database)

#Get prefix in string
  def prefix_str(self,ctx):
    if not ctx.guild: return self.default_prefix
    return db[str(ctx.guild.id)].get("custom_prefix", self.default_prefix)

#Self pinging
  @tasks.loop(seconds=200,reconnect=True)
  async def pinging(self):
    from requests import head
    head("https://Music-can-weep.alt-accounts.repl.co")
    global is_down
    if not is_down:
      is_down = True
      megasus = head('https://mega-sus-5-star.alt-accounts.repl.co')
      if megasus.status_code!=200:
        owner = await self.BOT.fetch_user(self.BOT.owner_id)
        await owner.send("Mega sus is down L")
        print("MEga sus down L")

#Change activity / presence
  @tasks.loop(seconds=60,reconnect=True)
  async def changeBotPresence(self):
    from discord import Streaming,Game,Activity,ActivityType
    from random import choice as randomChoice

    presence = [
      Activity(type=ActivityType.listening, 
              name="Music 🎧~ | >>help"),
      Game(name=f"with {len(self.BOT.guilds)} servers | >>help"),
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

    self.log = self.BOT.get_channel(self.log_id)
    self.error_log = self.BOT.get_channel(self.error_log_id)

    cogs =["bot_admin","help","music"]
    for cog_name in cogs:
      self.BOT.load_extension(f'cogs.{cog_name}')

    #Message that tell us we have logged in
    await self.log.send(f"`{str(dt.now())[:-7]}` - Logged in as {self.BOT.user.mention} ( running in {len(self.BOT.guilds)} servers ) ;")

    #Start a loop
    self.changeBotPresence.start()
    
    #Pinging the bot
    self.pinging.start()


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
    log_channel = self.BOT.get_channel(self.log_id)
    discord_error = commands.errors
    print(commandError)
    await log_channel.send(f"`{str(dt.now())[:-7]}` - {ctx.author} triggered an error : `{str(commandError)}` in [{ctx.guild}] ;")

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

    # elif isinstance(commandError,discord_error.NotFound):
    #   print("Deleted or idk")

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
      else:
        await self.error_log.send(f"```arm\n{str(dt.now())[:-7]} - Unknwon Error detected : {commandError}\n```")
    #or else it would be the code's error
    else:
      await ctx.reply(f"An error has been captured :\n```coffee\n{commandError}\n```")
      await self.error_log.send(f"```arm\n{str(dt.now())[:-7]} - Unknwon Error detected : {commandError}\n```")
    

#Server joining
  @commands.Cog.listener()
  async def on_guild_join(self,guild):
    log_channel = self.BOT.get_channel(self.log_id)
    link = await guild.system_channel.create_invite(xkcd=True, max_age = 0, max_uses = 0)
    await log_channel.send(f"`{str(dt.now())[:-7]}` - I joined `{guild.name}` ( ID :{guild.id}) <@{self.BOT.owner_id}>;\{link}")

    #welcome embed
    from discord import Embed
    welcome_embed = Embed(
      title = "**🙌🏻 Thanks for inviting me to this server !**",
      description = f"Type {self.default_prefix}command for some instruction !",
    )
      # description = f"This server looks cool! With me, we can make it even better !\nYou are now able to vibe with others in the wave of music 🎶~\n\nyou can already start using the commands ! ( Type {self.default_prefix}help if you need some instructions )")

    #Search for a channel to send the Embed
    for channel in guild.text_channels:
      if channel.permissions_for(guild.me).send_messages:
        await channel.send(embed=welcome_embed)
        break

    #Settle the database for the server
    db[str(guild.id)] = self.default_database