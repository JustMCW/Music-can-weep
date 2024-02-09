""""""

import discord
import aiohttp

import traceback
import datetime

from keys import *
from typechecking import *
from discord.utils import MISSING
from discord.ext import commands

DISABLE_LOGGING = False

async def _log(
    url: str, 
    message: str=MISSING, 
    **options
):
    if DISABLE_LOGGING:
        return
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(url,
                                           session=session)
        await webhook.send(content=message, **options)

async def log(
    message: str=MISSING, 
    **options
):
    if not ERROR_WEBHOOK_URL and not TEST_MODE:
        raise RuntimeError("Webhook Url is missing ! Enable test mode to dismiss this error.")

    await _log(LOGGER_WEBHOOK_URL, message, **options)
        

async def ctx_log(ctx: commands.Context, *args, **kwargs):
    guild = ctx.guild  
    if guild:
        if guild.id == TEST_SERVER_ID:
            pass

    await log(
        username="Context Logger",

        embed=discord.Embed(
            title=f"{guild.name+' | ' if guild else ''}{ctx.channel}",
            description=f"**Used the {ctx.command} command ({ctx.message.content})**",
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=datetime.datetime.now()
        ).set_author(
            name=ctx.author,
            icon_url=ctx.author.display_avatar
        )
    )

async def interaction_log(interaction : discord.Interaction, **kwargs):
    guild = ensure_exist(interaction.guild)
    data  = ensure_exist(interaction.data) 

    if guild.id == TEST_SERVER_ID:
        pass

    custom_id = data.get('custom_id')
    desc = f"**Pressed the {custom_id} button**" if custom_id else f"**Used the {data.get('name')} slash command**"
    await log(
        username="Button Logger",

        embed= discord.Embed(
            title = f"{guild.name+' | ' if guild else ''}{interaction.channel}",
            description = desc,
            color=discord.Color.from_rgb(255,255,255),
            timestamp = datetime.datetime.now()
        ).set_author(
            name =interaction.user,
            icon_url= interaction.user.display_avatar
        ),
        
        **kwargs
    )

async def event_log(message: str, **kwargs):
    await log(
        username="Event Logger",
        embed=discord.Embed(title=message,
                            color=discord.Color.from_rgb(255, 255, 255),
                            timestamp=datetime.datetime.now(), **kwargs),
    )

async def error_log(error: BaseException, ctx=None, **kwargs):
    if not ERROR_WEBHOOK_URL and not TEST_MODE:
        raise RuntimeError("Webhook Url is missing ! Enable test mode to dismiss this error.")

    try:
        raise error
    except:
        await _log(
            url = ERROR_WEBHOOK_URL,
            username="Error Logger",
            message=f"<@{OWNER_ID}>", # ping myself lol
            embed=discord.Embed(title=f"ERROR : {error.__class__.__name__}" if not ctx else f"Triggered at {ctx.guild.name}|{ctx.channel.name} by {ctx.author.name}",
                                description=f"```python\n{traceback.format_exc()}```",
                                color=discord.Color.from_rgb(255, 10, 10),
                                timestamp=datetime.datetime.now(), **kwargs),
        )
        
