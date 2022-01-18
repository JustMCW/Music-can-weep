from discord import Activity,ActivityType,Embed
from datetime import datetime as dt
from discord_components import DiscordComponents
from discord.ext import commands
from replit import db
from replies import replies

PingTime = 60 * 30

#--------------------#

class events(commands.Cog,replies):
  def __init__(self,bot,info):
    self.bot = bot
    self.default_prefix = info.default_prefix
    self.default_database = info.default_database
    self.log_id = info.cmd_log_id
    self.error_log_id = info.error_log_id
    self.cmd_aliases_list = []

#Checking database
  def checkDatabase(self):
    for guild in self.bot.guilds:
      if str(guild.id) not in db.keys():
        print(guild," lacking Database lol")
        db.set(str(guild.id),self.default_database)

#Get prefix in string
  def prefix_str(self,ctx):
    if not ctx.guild: return self.default_prefix
    return db[str(ctx.guild.id)].get("custom_prefix", self.default_prefix)

#Set up
  @commands.Cog.listener()
  async def on_ready(self):
    from os import system
    system("clear")
    self.checkDatabase()
    DiscordComponents(self.bot)

    #Add cogs / commands
    from cogs.music import music_commands
    from cogs.help import support_commands
    from cogs.bot_admin import bot_admin_commands
    
    self.bot.add_cog(music_commands(self.bot,self.log_id))
    self.bot.add_cog(support_commands(self.bot,self.log_id))
    self.bot.add_cog(bot_admin_commands(self.bot,self.log_id))
  
    #Change activity / presence
    await self.bot.change_presence(
      activity=Activity(
        type=ActivityType.listening, 
        name="Music 🎧~",
      )
    )

    #Message that tell us we hav logged in
    log_channel = self.bot.get_channel(self.log_id)
    loggin_msg = await log_channel.send(f"`{str(dt.now())[:-7]}` - Logged in as {self.bot.user.mention} ( running in {len(self.bot.guilds)} servers ) ;")

    #Reboot the bot
    from asyncio import sleep
    from requests import get
    while True:
      await sleep(PingTime)
      response = get("https://Music-can-weep.alt-accounts.repl.co")
      if response.status_code != 200:
      #   await loggin_msg.reply(f"`{str(dt.now())[:-7]}` - Successfully auto pingged;")
      # else:
        await loggin_msg.reply(f"`{str(dt.now())[:-7]}` - Failed to ping, error:[{response.status_code}];")
    

  def guess_the_command(self,wrong_cmd,prefix):

    #Create a command list without admin commands
    clientCmdList = []
    [clientCmdList.extend(cog.get_commands()) for cog in self.bot.cogs.values() if 'admin' not in cog.qualified_name]
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

#Error handling
  @commands.Cog.listener()
  async def on_command_error(self,ctx,eror):
    log_channel = self.bot.get_channel(self.log_id)
    error_type = commands.errors

    #Invaild command
    if isinstance(eror,error_type.CommandNotFound):
      wrong_cmd = str(eror)[9:-14]
      await ctx.reply(super().command_not_found_msg.format(self.guess_the_command(wrong_cmd,self.prefix_str(ctx))))

    #Not in server
    elif isinstance(eror,error_type.NoPrivateMessage):
      await ctx.reply(super().not_in_server_msg)

    #User missing permission
    elif isinstance(eror,error_type.NotOwner) or isinstance(eror,error_type.MissingPermissions):
      await ctx.reply(super().missing_perms_msg)
    #Bot missing permsion
    elif isinstance(eror,error_type.BotMissingPermissions):
      await ctx.reply(super().bot_lack_perm_msg)

    #User missing command argument
    elif isinstance(eror,error_type.MissingRequiredArgument):
      await ctx.reply(super().missing_arug_msg.format(str(eror)[:-40]))

    #User not found
    elif isinstance(eror,error_type.UserNotFound):
      await ctx.reply(super().user_not_found_msg)
    #Channel not found
    elif isinstance(eror,error_type.ChannelNotFound):
      await ctx.reply(super().channel_not_found_msg)

    #Custom Errors
    elif isinstance(eror,error_type.CommandInvokeError):
      error_name = str(eror)[29:-2]
      if "UserNotInVoiceChannel" == error_name: await ctx.reply(super().user_not_in_vc_msg)
      elif "NotInVoiceChannel" == error_name: await ctx.reply(super().bot_not_in_vc_msg)
      elif "NoAudioPlaying" == error_name: await ctx.reply(super().not_playing_msg)
      elif "BotMissingPermission" == error_name: await ctx.reply(super().bot_lack_perm_msg)
      else: await self.bot.get_channel(self.error_log_id).send(f"```arm\n{str(dt.now())[:-7]} - Unknwon Error detected : {eror}\n```")

    #or else it would be our code's error
    else: 
      await self.bot.get_channel(self.error_log_id).send(f"```arm\n{str(dt.now())[:-7]} - Unknwon Error detected : {eror}\n```")
    await log_channel.send(f"`{str(dt.now())[:-7]}` - {ctx.author} triggered an error : `{str(eror)}` ;")

#Server joining
  @commands.Cog.listener()
  async def on_guild_join(self,guild):
    log_channel = self.bot.get_channel(self.log_id)
    link = await guild.system_channel.create_invite(xkcd=True, max_age = 0, max_uses = 0)
    await log_channel.send(f"`{str(dt.now())[:-7]}` - I joined `{guild.name}` ( ID :{guild.id}) <@{self.bot.owner_id}>;")
    await log_channel.send(link)

    #Embed
    welcome_embed = Embed(
      title = "**🙌🏻 Thanks for inviting me to this server !**",
      description = "This server looks cool! With me, we can make it even better !\nYou are now able to vibe with others in the wave of music 🎶~\n\nyou can already start using the commands ! (Type ;help if you need instructions)")

    #Search for a channel to send
    for channel in guild.text_channels:
      if channel.permissions_for(guild.me).send_messages:
        await channel.send(embed=welcome_embed)
        break

    #Settle the database
    db[str(guild.id)] = self.default_database