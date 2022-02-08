#These commands are for me to test stuff (and thats why i add "_" in front of it)

from discord.ext import commands
import discord
from replit import db

class bot_admin_commands(commands.Cog):
  def __init__(self,bot):
    print("ADMIM commands is ready")
    self.bot = bot

  @commands.is_owner()
  @commands.command()
  async def _say(self,ctx,*,msg):
    await ctx.send(msg)
    print(msg)
  
  @commands.is_owner()
  @commands.command()
  async def _all_server(self,ctx):
    guildTable = ""
    for guild in self.bot.guilds:
      guildTable+=f"{guild.name} : {guild.id}\n"
    await ctx.send(guildTable)

  @commands.is_owner()
  @commands.command(aliases = ["_restartbot","_reset"])
  async def _update(self,ctx):
    await ctx.reply(f"✅ **Restarting - {self.bot.user.mention} ⚙️**")

    #restart / execute the code again
    from os import execv
    from sys import executable,argv
    execv(executable, ['python'] + argv)

  @commands.is_owner()
  @commands.command(aliases=["_si"])
  async def _serverinfo(self,ctx,id:int):
    guild = self.bot.get_guild(id)
    if guild:
      serin = discord.Embed(
        title=guild.name,
        color=discord.Color.random(),
        )
      #print([member.display_name for member in guild.members])
      serin.add_field(name="Founder 🛠:",value =str(guild.owner), inline=True)
      serin.add_field(name="Created at 📅:",value =str(guild.created_at)[:-16],                   inline=True)
      serin.add_field(name="Location 🌍:",value =str(guild.region), inline=True)
      serin.add_field(name="ID #️⃣", value=guild.id, inline=True)

      serin.add_field(name="Members 👨‍👩‍👦",
                      value =','.join([m.mention for m in guild.members if not m.bot]) or "None" ,
                      inline=False)
      serin.add_field(name="Bots 🤖",
                      value =','.join([m.mention for m in guild.members if m.bot]) or "None",                        
                      inline=False)
      serin.add_field(name="Roles ☑️",
                      value =",".join([role.name for role in guild.roles]) or "None", 
                      inline=False)
      
      serin.add_field(name="Text channels 💬",
                      value =",".join([txtchan.name for txtchan in guild.text_channels]), 
                      inline=False)
      serin.add_field(name="Voice channels 🔊",
                      value =",".join([vc.name for vc in guild.voice_channels]) or "None",
                      inline=False)
      serin.add_field(name="Emojis 😏",
                      value =",".join([f"<:{emoji.name}:{emoji.id}>" for emoji in guild.emojis]) or "None" , 
                      inline=False)
      # <:youtube_icon:937854541666324581>
      #serin.set_thumbnail(url = guild.owner.avator_url)
      serin.set_thumbnail(url=guild.icon_url)
      await ctx.reply(embed=serin)
    else: await ctx.reply("Failed to get guild")

  @commands.is_owner()
  @commands.command(aliases=["_allfavourties","_allfavs"])
  async def _showallfavourties(self,ctx):
    for id in db["favourites"]:
      favouritesList = "\n".join(list(db["favourites"][id].keys()))
      await ctx.send(f'<@{id}> :\n{favouritesList}')