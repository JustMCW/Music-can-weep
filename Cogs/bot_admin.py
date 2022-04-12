#These commands are for me to test stuff (and thats why i add "_" in front of it)

from discord.ext import commands
import discord
# from replit import db

class bot_admin_commands(commands.Cog):
    def __init__(self,bot):
      print("ADMIM commands is ready")
      self.bot = bot

    @commands.is_owner() 
    @commands.group()
    async def admin(self,ctx:commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.reply(f"Haha you idk the subcommands : {','.join([f'{command.name},{str(command.clean_params)}' for command in ctx.command.walk_commands()])}")
    
    @commands.is_owner() 
    @admin.command()
    async def test(self,ctx:commands.Context,*_):
        msg:discord.Message = await ctx.reply("This is a testing command.")
        print(msg.reference.message_id)
        # await ctx.invoke(ctx.bot.get_command("admin shutdown"))

    @admin.command()
    async def cleanup(self,ctx):
        try:
            ctx.guild.voice_client.source.cleanup()
        except AttributeError:
            await ctx.reply("Not playing")
        else:
            await ctx.reply("Success")


    @commands.is_owner() 
    @admin.command()
    async def say(self,ctx,*,message):
        await ctx.send(message)
        print(message)
    
    @commands.is_owner()
    @admin.command()
    async def all_server(self,ctx):
        guildTable = ""
        for guild in self.bot.guilds:
          guildTable+=f"{guild.name} : {guild.id}\n"
        await ctx.send(guildTable)

    @commands.is_owner()
    @admin.command(aliases = ["restartbot","reset"])
    async def update(self,ctx):
        await ctx.reply(f"✅ **Restarting - {self.bot.user.mention} ⚙️**")

        #restart / execute the code again
        from os import execv
        # system("pip3 freeze --local |sed -rn 's/^([^=# \\t\\\][^ \\t=]*)=.*/echo; echo Processing \1 ...; pip3 install -U \1/p' |sh")
        from sys import executable,argv
        execv(executable, ['python'] + argv)

    @admin.command(aliases = ["sd"])
    async def shutdown(self,ctx):
        await ctx.reply("Sayonara !")
        await self.bot.close()

    @commands.is_owner()
    @admin.command(aliases=["si","showserver"])
    async def serverinfo(self,ctx,id:int):
      guild = self.bot.get_guild(id)
      if guild:
        serin = discord.Embed(
          title=guild.name,
          color=discord.Color.random(),
          )
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
        
        #serin.set_thumbnail(url = guild.owner.avator_url)
        serin.set_thumbnail(url=guild.icon_url)
        await ctx.reply(embed=serin)
      else: 
        await ctx.reply("Failed to get guild")

    # @commands.is_owner()
    # @admin.command(aliases=["allfavourties","allfavs"])
    # async def showallfavourties(self,ctx):
    #   for id in db["favourites"]:
    #     favouritesList = "\n".join(list(db["favourites"][id].keys()))
    #     await ctx.send(f'<@{id}> :\n{favouritesList}')

def setup(BOT):
    BOT.add_cog(bot_admin_commands(BOT))