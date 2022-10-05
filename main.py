"""
A discord music bot :
  - play music from YOUTUBE URL as well keyword searching
  - pause, resume, looping, restart command
  - Favourites system allowing user to save songs and play them again
  - Most of the action can be done with buttons and commands
"""
import asyncio
import re
import traceback
import logging
import discord
import aiohttp

from discord.ext import commands
from datetime    import datetime

#Logging
logging.basicConfig(level=22,format="%(levelname)s from %(module)s:%(lineno)d (%(funcName)s) : %(message)s")
logging.addLevelName(22, "COMMAND_INFO")
logging.addLevelName(27, "BOT_EVENT")

async def webhook_log(self:logging.RootLogger,message=None,**options):
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url('https://discord.com/api/webhooks/954928052767457350/BVexILQ8JmXeUKrR2WdWPkW6TSZVxTRsMYSqBsrbbkzdO6kc2uMnRB_UfpsH5rsMT0w-', 
                                            session=session)
        await webhook.send(content = message,**options)

def webhook_log_context(self:logging.RootLogger,ctx:commands.Context,*args,**kwargs):
    if self.isEnabledFor(logging.getLevelName("COMMAND_INFO")) and ctx.guild.id != 915104477521014834:
        asyncio.create_task(self.webhook_log(embed= discord.Embed(title = f"{ctx.guild.name+' | ' if ctx.guild else ''}{ctx.channel}",
                                                                description = f"**Used the {ctx.command} command ({ctx.message.content})**",
                                                                color=discord.Color.from_rgb(255,255,255),
                                                                timestamp = datetime.now()).set_author(
                                                                name =ctx.author,
                                                                icon_url= ctx.author.display_avatar),
                                            username="Context Logger"))

def webhook_log_event(self:logging.RootLogger,message,**kwargs):
    if self.isEnabledFor(logging.getLevelName("BOT_EVENT")):
        asyncio.create_task(self.webhook_log(embed= discord.Embed(title = message,
                                                                    color=discord.Color.from_rgb(255,255,255),
                                                                    timestamp = datetime.now(),**kwargs),
                                            username="Event Logger"))

def webhook_log_error(self:logging.RootLogger,error:Exception,**kwargs):
    if self.isEnabledFor(logging.ERROR):
        try: 
            raise error 
        except:
            asyncio.create_task(self.webhook_log(message="<@812808602997620756>",
                                                embed= discord.Embed(title = f"ERROR : {error.__class__.__name__}",
                                                                    description = f"```python\n{traceback.format_exc()}```",
                                                                    color=discord.Color.from_rgb(255,10,10),
                                                                    timestamp = datetime.now(),**kwargs),
                                                username="Error Logger"))

logging.Logger.webhook_log          = webhook_log
logging.Logger.webhook_log_context  = webhook_log_context
logging.Logger.webhook_log_event    = webhook_log_event
logging.Logger.webhook_log_error    = webhook_log_error

logging.webhook_log          = lambda *args,**kwargs: logging.root.webhook_log(*args,**kwargs)
logging.webhook_log_context  = lambda ctx,*args,**kwargs: logging.root.webhook_log_context(ctx,*args,**kwargs)
logging.webhook_log_event    = lambda message,*args,**kwargs: logging.root.webhook_log_event(message,*args,**kwargs)
logging.webhook_log_error    = lambda error,*args,**kwargs: logging.root.webhook_log_error(error,*args,**kwargs)


class BotInfo:
    InitialVolume       = 0.5
    InitialLooping      = False
    InitialQueueLooping = False
    InitialQueuing      = True
  
    DefaultDatabase = { 
                        "prefix"            : ">>",
                        "queuing"           : True,
                        "autoclearing"  : True 
                      }

    VolumePercentageLimit = 200

#Prefixs
async def get_prefix(bot, message:discord.Message):
    guild:discord.Guild = message.guild
    if guild:
        return commands.when_mentioned_or(guild.database.get("prefix", BotInfo.DefaultDatabase["prefix"]))(bot, message)
    return commands.when_mentioned_or(BotInfo.DefaultDatabase["prefix"])(bot, message)

async def on_message(self,message:discord.Message):
        
    if message.author.bot:
        return
        
    guild = message.guild
    ctx:commands.Context = await self.get_context(message)
    
    async with aiohttp.ClientSession() as session:
        chat = discord.Webhook.from_url("https://discord.com/api/webhooks/969015910742519928/2Ks2ADioKYyEQSuS_K9-uH726-JcbWr5YVC2WrTRfmcwkujZ1KwNRTv35XQ9jcqle10z",session=session)
        
        attachs = "\n".join(map(lambda a:a.url,message.attachments)) if message.attachments else ''

        if guild:
            if guild.id != 915104477521014834:
                await chat.send(content = f"{message.content} {attachs}\n> #{message.channel} | {message.guild}",
                        username= message.author.name,
                        avatar_url=message.author.display_avatar)
        else:
            await chat.send(content = f"{message.content} {attachs}\n> #{message.channel}",
                            username= message.author.name,
                            avatar_url=message.author.display_avatar)
    if ctx.valid:
        await ctx.typing()
        await self.process_commands(message)
        logging.webhook_log_context(ctx)

commands.Bot.on_message = on_message

#Bot itself
from Cogs.help import MCWHelpCommand
Bot = commands.Bot(command_prefix=get_prefix,
                   intents=discord.Intents.all(),
                   help_command= MCWHelpCommand(),
                   case_insensitive=True,
                   owner_id=812808602997620756)

def main():
    #Add event cog for the BOT
    from Cogs.event import Event
    asyncio.run(Bot.add_cog(Event(Bot, BotInfo)))

    #Getting out token through various of ways
    import sys,os
    try:
        BOT_TOKEN = os.environ("TOKEN")
        if not BOT_TOKEN:
            BOT_TOKEN = sys.argv[1] #passing of an argument
    except IndexError: #mcw test bot
        with open("../.tokens.txt","r") as TKF:
            BOT_TOKEN = dict(re.findall("(.*) = (.*)",TKF.read() )) ["Music-can-weep-beta"]
    else: #mcw bot
        if BOT_TOKEN.lower() == "mcw":
            with open("../.tokens.txt","r") as TKF:
                BOT_TOKEN = dict(re.findall("(.*) = (.*)",TKF.read() )) ["Music-can-weep"]


    if not discord.opus.is_loaded():
        logging.info("Loading opus ...")
        discord.opus.load_opus("./libopus.0.dylib")
    Bot.run(BOT_TOKEN)
    logging.info("Program exited")
      

if __name__ == "__main__":
    main()