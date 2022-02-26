"""
A music bot :
  - play music from YOUTUBE URL as well keyword searching
  - pause, resume, looping, restart command
  - Favourites system allowing user to save songs and play them again
  - Most of the action can be done with buttons and commands
"""
from discord.ext import commands
from os import environ as secret
class BOT_INFO:
  default_prefix = ">>"
  bot_token = secret['token']
  #Logs_channel_id
  cmd_log_id = 923730161864704030
  error_log_id = 923761805619232798

  @classmethod
  def getLogsChannel(CLASS,BOT):
    return (
      BOT.get_channel(CLASS.cmd_log_id),
      BOT.get_channel(CLASS.error_log_id)
    )

  #Data Base
  default_database = {
    "custom_prefix" : default_prefix,
  }

#Prefix
from replit import db as database
async def get_prefix(bot,msg):
  guild = msg.guild
  print(f"{guild} - {msg.author} : {msg.content}")
  if guild: 
    return commands.when_mentioned_or(
      database[str(guild.id)].get(
        "custom_prefix",BOT_INFO.default_prefix
        )
      )(bot,msg)
  return commands.when_mentioned_or(BOT_INFO.default_prefix)(bot,msg)

#Bot itself
from discord import Intents

intents = Intents.default()  
intents.members = True  
intents.guilds = True
BOT = commands.Bot(command_prefix=get_prefix,
                  intents=intents,
                  help_command=None,
                  case_insensitive=True,
                  owner_id = 812808602997620756)

def main():
  print("Started the code")
  
  #Add event cog for the BOT
  from event import events
  BOT.add_cog(events(BOT,BOT_INFO))

  #Keep replit running so the BOT doesn't go offline
  from online import keep_online
  keep_online()

  #Run the BOT
  BOT.run(BOT_INFO.bot_token)

if __name__ == "__main__":
  main()