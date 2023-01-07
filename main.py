import asyncio
import logging

import discord
from discord.ext import commands

from key import *
from key import _extract_bot_token
import database.server as serverdb

#Logging
LOG_LEVEL = logging.INFO
FORMATTER = discord.utils._ColourFormatter()

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# Ouputing to the terminal
io_handler = logging.StreamHandler()
io_handler.setFormatter(FORMATTER)
io_handler.setLevel(LOG_LEVEL)
root_logger.addHandler(io_handler)

# Outputing to a file
if LOG_FILE:
    file_logger = logging.FileHandler(LOG_FILE)
    file_logger.setFormatter(logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', '%Y-%m-%d %H:%M:%S', style='{'))
    file_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_logger)

#Prefixs
async def get_prefix(bot, message:discord.Message):
    guild : discord.Guild = message.guild
    default_prfx = serverdb.defaultdb["prefix"]

    if guild:
        return commands.when_mentioned_or(guild.database.get("prefix", default_prfx))(bot, message)
    return commands.when_mentioned_or(default_prfx)(bot, message)

#Bot itself
from cogs.help import MCWHelpCommand
bot = commands.Bot(command_prefix=get_prefix,
                   intents=discord.Intents.all(),
                   help_command= MCWHelpCommand(),
                   case_insensitive=True)

@bot.event
async def on_ready():
    print(f"Running as \"{bot.user.name}#{bot.user.discriminator}\" [{bot.user.id}]")


    #Load the cogs for the bot
    cogs = [
        pyf.replace(".py", "") 
        for pyf in filter(
            lambda name: name.endswith(".py"), 
            os.listdir(f"{RUN_PATH}cogs")
        )
    ]

    ext_path = RUN_PATH.replace("/",".") if RUN_PATH != "./" else ''
    for cog_name in cogs:
        await bot.load_extension(
            f'{ext_path}cogs.{cog_name}',
            package=__package__
        )

    root_logger.info(f"Succuessfully loaded cogs : {cogs}")

    #Since we cannot edit it direactly
    bot.get_command("help").description = "☁️ Send guides about this bot and it's commands"
    bot.get_command("help").usage = "{}help play"

    # Start a background task  
    event = bot.get_cog("Event")
    bot.on_message = event.on_message
    event.changeBotPresence.start()


def main():
    root_logger.debug("Program started")


    TOKEN = _extract_bot_token()

    if not discord.opus.is_loaded():
        discord.opus.load_opus(OPUS_LIB)
        root_logger.info(f"Loaded opus from {OPUS_LIB}")

    #Just overwrite the reply function to never mention author.

    async def reply_without_mention(self : commands.Context, *args,**kwargs):
        kwargs["mention_author"] = False
        return await self.reply(*args,**kwargs)

    commands.Context.replywm = reply_without_mention
    
    bot.run(
        TOKEN,
        # log_level=logging.INFO,
        log_handler=None,
        root_logger=False
    )
    root_logger.debug("Program exited.")
      

if __name__ == "__main__":
    main()
