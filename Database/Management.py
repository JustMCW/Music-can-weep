import logging
import discord
import json
from main import BOT_INFO

DISCORD_SERVER_DATABASE = "Database/DiscordServers.json"

def auto_correct_databases(bot):
    """
    Loop through every discord server the bot is in,
    Check their key in the database exist
    Add missing keys if missed
    or the entire database is missing then set it to be the DefaultDatabase
    """
    with open(DISCORD_SERVER_DATABASE, "r+") as jsonf:
        data = json.load(jsonf)

        for guild in bot.guilds:
            ID = str(guild.id)

            #The server wasn't even found
            if ID not in data.keys():
                logging.info(guild, "lacking Database")
                data[ID] = BOT_INFO.DefaultDatabase
            elif data[ID].keys() != BOT_INFO.DefaultDatabase.keys():
                data[ID] = dict(
                    BOT_INFO.DefaultDatabase, **data[ID])
                logging.info(guild, "has incorrect key")
            # elif data[ID] == BOT_INFO.DefaultDatabase:
            #     data[ID] = None
            #     logging.info(f"Removed the database of {guild}")

        jsonf.seek(0)
        json.dump(data, jsonf, indent=3)

def read_servers_databases() -> dict:
    with open(DISCORD_SERVER_DATABASE,"r") as SVDBjson_r:
        data = json.load(SVDBjson_r)
    return data

def read_database_of(guild:discord.Guild) -> dict:
    return read_servers_databases().get(str(guild.id)) or BOT_INFO.DefaultDatabase

def overwrite_server_database(guild:discord.Guild,key:str,value) -> dict:
    data = read_servers_databases()
    data[str(guild.id)][key] = value

    with open(DISCORD_SERVER_DATABASE,"w") as SVDBjson_w:
        json.dump(data,SVDBjson_w,indent = 3)

    return data
