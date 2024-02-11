# allow us to do type annotations easier, such as forward declaration
from __future__ import annotations 

import logging

import discord
from discord.ext import commands

from database.server import read_database_of
from typechecking import *
from keys import *

#Logging
LOG_LEVEL = logging.WARNING
formatter = discord.utils._ColourFormatter()

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# Ouputing to the terminal
io_handler = logging.StreamHandler()
io_handler.setFormatter(formatter)
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
    guild = message.guild

    if guild:
        return commands.when_mentioned_or(
            read_database_of(guild)["prefix"]
        )(bot, message)
    return commands.when_mentioned_or(DEFAULT_PREFIX)(bot, message)

#Bot itself
from cogs.help import MCWHelpCommand
bot = commands.Bot(command_prefix=get_prefix,
                   intents=discord.Intents.all(),
                   help_command= MCWHelpCommand(),
                   case_insensitive=True)

@bot.event
async def on_ready():
    bot_user = ensure_exist(bot.user)
    logging.warning(f"Running as \"{bot_user.name}#{bot_user.discriminator}\" [{bot_user.id}]")

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
    help_cmd = ensure_exist(bot.get_command("help"))
    help_cmd.description = "☁️ Send guides about this bot and it's commands"
    help_cmd.usage = "{}help play"

    # Start a background task  
    event = bot.get_cog("Events") 
    bot.on_message = event.on_message #type: ignore
    event.changeBotPresence.start()#type: ignore


def main():
    if TEST_MODE:
        logging.warning("Test mode enabled.")

    # OPUS is required to decode audio
    if not discord.opus.is_loaded() and not TEST_MODE:
        discord.opus.load_opus(OPUS_LIB)
        root_logger.info(f"Loaded opus from {OPUS_LIB}")

    #Just overwriting the reply function to never mention author.
    async def reply_without_mention(self : commands.Context, *args, mention_author = False,**kwargs):
        if self.interaction is None:
            return await self.send(*args, reference=self.message, mention_author=mention_author, **kwargs)
        else:
            return await self.send(*args, mention_author=mention_author, **kwargs)
        # return await self.reply(*args,**kwargs)
    commands.Context.reply = reply_without_mention
    
    bot.run(
        BOT_TOKEN,
        log_handler=None,
        root_logger=False
    )
   
      

if __name__ == "__main__":
    root_logger.debug("Program started")
    main()
    root_logger.debug("Program exited.")
