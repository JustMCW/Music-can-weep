import discord
import json

# USER_DATABASE_ID   = 1008808177791414302
# SERVER_DATABASE_ID = 1008808263057424518

# user_database_channel   : discord.TextChannel = None
# server_database_channel : discord.TextChannel = None

DefaultDatabase = { 
                    "prefix"            : ">>",
                    "queuing"           : True,
                    "autoclearing"  : True 
                }

# #json Db
DISCORD_SERVER_DATABASE = "Database/DiscordServers.json"

def check_server_database(bot):
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
            if ID in data.keys():
                if data[ID].keys() != DefaultDatabase.keys():
                    data[ID] = dict(DefaultDatabase, **data[ID])
                    print(guild, "has incorrect key")

        jsonf.seek(0)
        json.dump(data, jsonf, indent=4)

def read_servers_databases() -> dict:
    with open(DISCORD_SERVER_DATABASE,"r") as SVDBjson_r:
        data = json.load(SVDBjson_r)
    return data

def read_database_of(guild:discord.Guild) -> dict:
    return read_servers_databases().get(str(guild.id)) or DefaultDatabase

def overwrite_server_database(guild:discord.Guild,key:str,value) -> dict:
    data = read_servers_databases()
    data[str(guild.id)][key] = value

    with open(DISCORD_SERVER_DATABASE,"w") as SVDBjson_w:
        json.dump(data,SVDBjson_w,indent = 4)

    return data
    
#New databasse function

# async def build_database_for(server_id:int,database:dict = None):

#     await server_database_channel.send(
#         content=json.dumps(
#             {
#                 str(server_id) : database or BOT_INFO.DefaultDatabase
#             },
#             indent=4
#         )
#     )

# async def read_database_of(guild:discord.guild) -> dict:
#     server_id = str(guild.id)

#     async for message in server_database_channel.history():
#         json_data = json.loads(message.content)
#         if json_data.get(server_id):
#             return json_data[server_id]
    
#     await build_database_for(server_id)
#     return BOT_INFO.DefaultDatabase

# async def overwrite_server_database(guild:discord.Guild,key:str,value:Any):
#     server_id = str(guild.id)

#     data = BOT_INFO.DefaultDatabase
#     message_object :discord.Message = None

#     async for message in server_database_channel.history():
#         json_data = json.loads(message.content)
#         if json_data.get(server_id):
#             data  =json_data[server_id]
#             message_object = message

#     data[key] = value

#     try:
#         await message_object.edit(content=json.dumps({server_id:data},indent=4))
    
#     #Message not found
#     except AttributeError:
#         await build_database_for(server_id,data)
#     except discord.errors.Forbidden:
#         print(message_object.author.display_name)

# async def check_server_database(bot:commands.Bot):

#     guild_ids  = list(map(lambda g:str(g.id), bot.guilds))
#     async for message in server_database_channel.history():
#         json_data : dict   = json.loads(message.content)
#         g_id : str = list(json_data.keys())[0]
#         if g_id in guild_ids:
#             if json_data[g_id].keys() == BOT_INFO.DefaultDatabase.keys():
#                 guild_ids.remove(g_id)
#             else:
#                 print(g_id,"lack key")
#                 message.edit(content=json.dumps(
#                     {
#                         g_id: dict(BOT_INFO.DefaultDatabase, **json_data[g_id])
#                     },
#                     indent=4
#                     )
#                 )


#     for g_id in guild_ids:
#         print(g_id,"lacks database")
#         await build_database_for(g_id)
#         # #The server wasn't even found
#         # if ID not in data.keys():
#         #     logging.info(guild, "lacking Database")
#         #     data[ID] = BOT_INFO.DefaultDatabase
#         # elif data[ID].keys() != BOT_INFO.DefaultDatabase.keys():
#         #     data[ID] = dict(
#         #         BOT_INFO.DefaultDatabase, **data[ID])
#         #     logging.info(guild, "has incorrect key")

# def initialize(bot):

#     global user_database_channel,server_database_channel

#     user_database_channel = bot.get_channel(USER_DATABASE_ID)
#     server_database_channel = bot.get_channel(SERVER_DATABASE_ID)

"""
discord text-channel-database plan :

Say we want to set my server prefix to '==',
We'll go into the server db channel
Look through messages starting at the bottom
until we find a message in which its key matches my server id, and saves that message

we convert the content of that message to a dictionary
changes the prefix key in the dictionary
edit the message with the new data
"""