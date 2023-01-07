""""""

import discord
import aiohttp
import asyncio

import traceback
import datetime

from key import *
from discord.ext import commands

DISABLE_LOGGING = True

async def _log(url : str, message=None, **options):
    if DISABLE_LOGGING:
        return
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(url,
                                           session=session)
        await webhook.send(content=message, **options)

async def log(message=None, **options):
    await _log(LOGGER_WEBHOOK_URL, message, **options)

async def ctx_log(ctx: commands.Context, *args, **kwargs):
    guild = ctx.guild  
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
    guild = interaction.guild
    if guild.id == TEST_SERVER_ID:
        pass

    await log(
        username="Button Logger",

        embed= discord.Embed(
            title = f"{guild.name+' | ' if guild else ''}{interaction.channel}",
            description = f"**Pressed the {interaction.data['custom_id']} button**",
            color=discord.Color.from_rgb(255,255,255),
            timestamp = datetime.datetime.now()
        ).set_author(
            name =interaction.user,
            icon_url= interaction.user.display_avatar
        ),
        
        **kwargs
    )
    
async def event_log(message, **kwargs):
    await log(
        username="Event Logger",
        embed=discord.Embed(title=message,
                            color=discord.Color.from_rgb(255, 255, 255),
                            timestamp=datetime.datetime.now(), **kwargs),
    )

async def error_log(error: Exception, **kwargs):
    try:
        raise error
    except:
        await _log(
            url = ERROR_WEBHOOK_URL,
            username="Error Logger",
            message=f"<@{OWNER_ID}>", # ping myself lol

            embed=discord.Embed(title=f"ERROR : {error.__class__.__name__}",
                                description=f"```python\n{traceback.format_exc()}```",
                                color=discord.Color.from_rgb(255, 10, 10),
                                timestamp=datetime.datetime.now(), **kwargs),
        )
        
