"""
A discord music bot :
  - play music from YOUTUBE URL as well keyword searching
  - pause, resume, looping, restart command
  - Favourites system allowing user to save songs and play them again
  - Most of the action can be done with buttons and commands
"""
from discord.ext import commands
import os
import json
import traceback
import logging
import discord
from datetime import datetime

webhook = discord.Webhook.from_url('https://discord.com/api/webhooks/954928052767457350/BVexILQ8JmXeUKrR2WdWPkW6TSZVxTRsMYSqBsrbbkzdO6kc2uMnRB_UfpsH5rsMT0w-', adapter=discord.RequestsWebhookAdapter())
chat = discord.Webhook.from_url("https://discord.com/api/webhooks/969015910742519928/2Ks2ADioKYyEQSuS_K9-uH726-JcbWr5YVC2WrTRfmcwkujZ1KwNRTv35XQ9jcqle10z",adapter=discord.RequestsWebhookAdapter())

#Logging
logging.basicConfig(level=26,format="%(levelname)s from %(module)s:%(lineno)d (%(funcName)s) : %(message)s")
logging.addLevelName(22, "COMMAND_INFO")
logging.addLevelName(27, "BOT_EVENT")

def webhook_log(self:logging.RootLogger,message=None,**options):
    webhook.send(content = message,**options)

def webhook_log_context(self:logging.RootLogger,ctx:commands.Context,*args,**kwargs):
    if self.isEnabledFor(logging.getLevelName("COMMAND_INFO")):
        self.webhook_log(embed= discord.Embed(title = f"{ctx.guild.name+' | ' if ctx.guild else ''}{ctx.channel}",
                                                    description = f"**{ctx.prefix}{ctx.command} {' '.join(ctx.args[2:])}**",
                                                    color=discord.Color.from_rgb(255,255,255),
                                                    timestamp = datetime.now()).set_author(
                                                    name =ctx.author,
                                                    icon_url= ctx.author.avatar_url),
                                username="Context Logger")

def webhook_log_event(self:logging.RootLogger,message,**kwargs):
    if self.isEnabledFor(logging.getLevelName("BOT_EVENT")):
        self.webhook_log(embed= discord.Embed(title = message,
                                            color=discord.Color.from_rgb(255,255,255),
                                            timestamp = datetime.now(),**kwargs),
                                username="Event Logger")

def webhook_log_error(self:logging.RootLogger,error:Exception,**kwargs):
    if self.isEnabledFor(logging.ERROR):
        try: 
            raise error
        except:
            self.webhook_log(embed= discord.Embed(title = f"ERROR : {error.__class__.__name__}",
                                                        description = traceback.format_exc(),
                                                        color=discord.Color.from_rgb(255,10,10),
                                                        timestamp = datetime.now(),**kwargs),
                                    username="Error Logger")


logging.Logger.webhook_log = webhook_log
logging.Logger.webhook_log_context = webhook_log_context
logging.Logger.webhook_log_event = webhook_log_event
logging.Logger.webhook_log_error = webhook_log_error

logging.webhook_log = lambda *args,**kwargs: logging.root.webhook_log(*args,**kwargs)
logging.webhook_log_context = lambda ctx,*args,**kwargs: logging.root.webhook_log_context(ctx,*args,**kwargs)
logging.webhook_log_event = lambda ctx,*args,**kwargs: logging.root.webhook_log_event(ctx,*args,**kwargs)
logging.webhook_log_error = lambda ctx,*args,**kwargs: logging.root.webhook_log_error(ctx,*args,**kwargs)


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
      "sync_lyrics": False,
      "auto_clear_queue":True,
    }



#Prefix
async def get_prefix(bot, msg:discord.Message):
    guild = msg.guild

    if guild and guild.id != 915104477521014834:
        chat.send(content = f"{msg.content}\n> #{msg.channel} | {msg.guild}",
                username= msg.author.name,
                avatar_url=msg.author.avatar_url,
                files=getattr(msg,"files",None))
    else: 
        chat.send(content = f"{msg.content}\n> #{msg.channel}",
                username= msg.author.name,
                avatar_url=msg.author.avatar_url,
                files=getattr(msg,"files",None))
    if guild:
        with open("Database/DiscordServers.json","r") as jsonfr:
            return commands.when_mentioned_or(json.load(jsonfr)[str(guild.id)].get("prefix", BOT_INFO.DefaultPrefix))(bot, msg)
    return commands.when_mentioned_or(BOT_INFO.DefaultPrefix)(bot, msg)


#Bot itself

from discord import Intents
from Cogs.help import MCWHelpCommand

intents = Intents.default()
intents.members = True
intents.guilds = True
BOT = commands.Bot(command_prefix=get_prefix,
                   intents=intents,
                   help_command=MCWHelpCommand(),
                   case_insensitive=True,
                   owner_id=812808602997620756)

def log_before_invoke(ctx):
    logging.webhook_log_context(ctx)
    return True

BOT.add_check(log_before_invoke)

def main():
    logging.debug("Started the code")

    #Add event cog for the BOT
    from Cogs.event import event
    BOT.add_cog(event(BOT, BOT_INFO))

    BOT_TOKEN = os.environ.get("TOKEN")
    
    if BOT_TOKEN is not None:
        logging.info("Running on cloud")
    else:
        logging.info("Running locally")
        import sys
        import re
        with open("../.tokens.txt","r") as TKF:
            if len(sys.argv) == 1:
                BOT_TOKEN = dict(re.findall("(.*) = (.*)",TKF.read() )) ["Music-can-weep-beta"]
            else:
                BOT_TOKEN = dict(re.findall("(.*) = (.*)",TKF.read() )) ["Music-can-weep"]

        from discord import opus
        if not opus.is_loaded():
            logging.debug("Loading opus ...")
            opus.load_opus("/Users/xwong/Documents/Daily/Learning/Computing/exe/libopus.0.dylib")


    BOT.run(BOT_TOKEN)
    logging.info("Program exited")
      


if __name__ == "__main__":
    main()