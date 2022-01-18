from discord.ext import commands
import discord
from replit import db

class bot_admin_commands(commands.Cog):
  def __init__(self,bot,log_id):
    self.bot = bot
    self.log= self.bot.get_channel(log_id)

  @commands.is_owner()
  @commands.command(aliases = ["restartbot","reset"])
  async def update(self,ctx):
    await ctx.reply(f"✅ **Successfully restarted {self.bot.user.mention} ⚙️**")

    #restart the replit / code
    from os import execv
    from sys import executable,argv
    execv(executable, ['python'] + argv)

  @commands.is_owner()
  @commands.command()
  async def show_all_db(self,ctx):
    for i,v in db.items():
      if i!="favourites":
        print(i,v)

  @commands.is_owner()
  @commands.command(aliases=["si"])
  async def serverinfo(self,ctx,id:int):
    guild = self.bot.get_guild(id)
    if guild:
      serin = discord.Embed(
        title=guild.name,
        color=discord.Color.random())
      #print([member.display_name for member in guild.members])
      serin.add_field(name="Founder 🛠:",value =str(guild.owner), inline=False)
      serin.add_field(name="Created at 📅:",value =str(guild.created_at)[:-16], inline=False)
      serin.add_field(name="Location 🌍:",value =str(guild.region), inline=False)
      serin.add_field(name="ID #️⃣", value=guild.id, inline=False)
      serin.add_field(name="Members 👨‍👩‍👦",value =str(len([m for m in guild.members if not m.bot])) , inline=True)
      serin.add_field(name="Bots 🤖",value =str(len([m for m in guild.members if m.bot]) ), inline=True)
      serin.add_field(name="Roles ☑️",value =str(len(guild.roles)-2), inline=True)
      serin.add_field(name="Text channels 💬",value =str(len(guild.text_channels)), inline=True)
      serin.add_field(name="Voice channels 🔊",value =str(len(guild.voice_channels)), inline=True)
      serin.add_field(name="Emojis 😏",value =str(len(guild.emojis)), inline=True)
      #serin.set_thumbnail(url = guild.owner.avator_url)
      serin.set_image(url=guild.icon_url)
      await ctx.reply(embed=serin,mention_author=False)
    else: await ctx.reply("Failed to get guild")

  @commands.is_owner()
  @commands.command(aliases=["inv"])
  async def invite(self,ctx,id:int):
    guild = self.bot.get_guild(id)
    if not guild: return print("guild not found")
    channel =guild.system_channel
    print(dir(channel))
    link =await channel.create_invite()
    await ctx.send(link)

  @commands.is_owner()
  @commands.command(aliases=["allfavourties","allfavs"])
  async def showallfavourties(self,ctx):
    for id in db["favourites"]:
      print(id,db["favourites"][id])