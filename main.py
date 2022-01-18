#Hey there ! Why are you here ?

from discord.ext import commands

#Prefix
default_prefix = ">>"
from replit import db as database
async def get_prefix(bot,msg):
  guild = msg.guild
  if guild: 
    id = str(guild.id)
    return commands.when_mentioned_or(database[id].get("custom_prefix", default_prefix))(bot,msg)
  return commands.when_mentioned_or(default_prefix)(bot,msg)

#Bot itself
from discord import Intents
intents = Intents.default()  
intents.members = True  
intents.guilds = True

bot = commands.Bot(
  command_prefix=get_prefix,
  intents=intents,
  help_command=None,
  case_insensitive=True,
  owner_id = 812808602997620756
)

class bot_info:
  default_prefix = default_prefix
  #Logs_channel_id
  cmd_log_id = 923730161864704030
  error_log_id = 923761805619232798

  #Data Base
  default_database = {
    "custom_prefix" : default_prefix,
  }

#Events
from event import events
bot.add_cog(events(bot,bot_info))

# #On message
# @bot.event
# async def on_message(message):
#   ctx = await bot.get_context(message)
#   if ctx.author != bot.user: await bot.invoke(ctx)

#Keep replit running
from online import keep_alive as keep_online
keep_online()

#Run the bot
from os import environ as secret
bot.run(secret['token'])