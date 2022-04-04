"""
A discord music bot :
  - play music from YOUTUBE URL as well keyword searching
  - pause, resume, looping, restart command
  - Favourites system allowing user to save songs and play them again
  - Most of the action can be done with buttons and commands
"""

from discord.ext import commands
import os,json,re

class BOT_INFO:
    DefaultPrefix = ">>"
  
    InitialVolume = 0.5
  
    InitialLooping = False
    InitialQueueLooping = False
  
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

    # from discord import opus
    # if not opus.is_loaded():
    #     print("Loading opus ...")
    #     opus.load_opus("/Users/xwong/Documents/Daily/Learning/Computing/exe/libopus.0.dylib")
    
    # try:
    #     with open("../.tokens.txt","r") as TKF:
    #         BOT_TOKEN = dict(re.findall("(.*) = (.*)",
    #                                     TKF.read() )) ["Music-can-weep-beta"]
    # except FileNotFoundError:
    #     from boto.s3.connection import S3Connection
    #     BOT_TOKEN = S3Connection(os.environ['TOKEN'])
    #     print("Successfully loaded token from heroku var")
    # else:
    #     print("Successfully loaded token from token file ")
        

    BOT.run("OTE5NTk3MjgwNTIzMzQ1OTYx.YbYHtA.loRdonvp56WuLDo5vJbdqaC7zGE")
    print("Program exited")
      


if __name__ == "__main__":
    main()