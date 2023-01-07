import discord
import json

from keys import *

defaultdb = { 
    "prefix"        : DEFAULT_PREFIX,
    "queuing"       : True,
    "autoclearing"  : True 
}


def check_server_database(bot):
    """
    Loop through every discord server the bot is in,
    Check their key in the database exist
    Add missing keys if missed
    or the entire database is missing then set it to be the defaultdb
    """

    with open(SERVER_DATABASE, "r+") as jsonf:
        data = json.load(jsonf)

        for guild in bot.guilds:
            ID = str(guild.id)

            #The server wasn't even found
            if ID in data.keys():
                if data[ID].keys() != defaultdb.keys():
                    data[ID] = dict(defaultdb, **data[ID])
                    print(guild, "has incorrect key")

        jsonf.seek(0)
        json.dump(data, jsonf, indent=4)

def read_servers_databases() -> dict:
    with open(SERVER_DATABASE,"r") as SVDBjson_r:
        data = json.load(SVDBjson_r)
    return data

def read_database_of(guild:discord.Guild) -> dict:
    return read_servers_databases().get(str(guild.id)) or defaultdb

def overwrite_server_database(guild:discord.Guild,key:str,value) -> dict:
    data = read_servers_databases()
    data[str(guild.id)][key] = value

    with open(SERVER_DATABASE,"w") as SVDBjson_w:
        json.dump(data,SVDBjson_w,indent = 4)

    return data