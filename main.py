
"""
A discord music bot :
  - play music from YOUTUBE URL as well keyword searching
  - pause, resume, looping, restart command
  - Favourites system allowing user to save songs and play them again
  - Most of the action can be done with buttons and commands
"""
from discord.ext import commands
import os,json

# with open("TOKEN.txt","r") as tkf:
#   BOT_TOKEN = tkf.readlines()[0].strip()

class BOT_INFO:
  #OTE5NTk3MjgwNTIzMzQ1OTYx.YbYHtA.loRdonvp56WuLDo5vJbdqaC7zGE
    DefaultPrefix = ">>"
  
    InitialVolume = 0.5
  
    InitialLooping = False
    InitialQueueLooping = True
  
    InitialQueuing = True
  
    #Data Base
    DefaultDatabase = {
      "prefix":  DefaultPrefix,
      "queuing": InitialQueuing,
    }


#Prefix


async def get_prefix(bot, msg):
    guild = msg.guild
    print(f"{guild} - {msg.author} : {msg.content}")
    if guild:
      with open("Database/DiscordServers.json","r") as jsonfr:
        return commands.when_mentioned_or(json.load(jsonfr)[str(guild.id)].get("prefix", 
                                                                               BOT_INFO.DefaultPrefix))(bot, msg)
    return commands.when_mentioned_or(BOT_INFO.DefaultPrefix)(bot, msg)


#Bot itself

from discord import Intents

intents = Intents.default()
intents.members = True
intents.guilds = True
BOT = commands.Bot(command_prefix=get_prefix,
                   intents=intents,
                   help_command=None,
                   case_insensitive=True,
                   owner_id=812808602997620756)


def main():
    print("Started the code")

    #Add event cog for the BOT
    from event import events
    BOT.add_cog(events(BOT, BOT_INFO))

    from discord import opus
    if not opus.is_loaded():
      print("Loading opus ...")
      opus.load_opus("/Users/xwong/Desktop/lib/libopus.dylib")
    
    BOT.run("OTMxMDA3NTcxOTQ1NDcyMDcx.Yd-KXg.OZYMCXnD2PlT8-m3pTM39jSoYUs")
      


if __name__ == "__main__":
    main()