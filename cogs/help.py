#This script is relativly easy , try to figure it out yourself :P

import discord
from datetime import datetime as dt
from discord.ext import commands
from replit import db
from discord_components import Button, ButtonStyle , ActionRow 

class support_commands(commands.Cog):
  def __init__(self,bot,log_id):
    self.bot = bot
    self.log = self.bot.get_channel(log_id)
    super().__init__()
    
  @commands.command(aliases = ["how","setup","h"],description = "👍🏻 Send a message to teach you how to use me")
  async def help(self,ctx):
    await self.log.send(f"`{str(dt.now())[:-7]}` - {ctx.author} just used help command ;")

    if ctx.guild: await ctx.reply("👍🏻 Check your DM")
    owner = await self.bot.fetch_user(self.bot.owner_id)
    help_embed = discord.Embed(
      title = "**All about Music Can Weep**",
      description = f"**👋 Hello There ! Glad that you are reading this , highly appreciated !**\n\n By inviting me to your server , you will be able to play music and vibe with your friends ! 🎶 \nI also offers a cool and useful **BUTTON FEATURE **⏸ ▶\n so you don't have to type to interact with the audio! \n\nTo start up with , invite me to your discord server !\nTap the Button below to invite me 🔗\n\n What are the commands ? simply type `;cmd` or tap the button below for a list of commands !\n\n**Lastly , if you need further more help or faced bugs / glitches , contact {owner.mention} / {owner}**",color = discord.Color.from_rgb(255,255,255),
      timestamp=dt.now())

    help_embed.set_thumbnail(url = self.bot.user.avatar_url)
    DM = await ctx.author.create_dm()
    help_buttons = [
      ActionRow(
        Button(label = "show me the command list",style = ButtonStyle.blue,custom_id = "cmd",emoji = "📄"),
        Button(label = "invite me to your server !",style = ButtonStyle.URL,url = "https://discord.com/api/oauth2/authorize?client_id=919597280523345961&permissions=274881170944&scope=bot",emoji = "🔗"))]
    inv_only_button = [
      Button(label = "invite me to your server !",
      style = ButtonStyle.URL,
      url = "https://discord.com/api/oauth2/authorize?client_id=919597280523345961&permissions=274881170944&scope=bot",
      emoji = "🔗")
    ]

    help_msg = await DM.send(embed = help_embed,components = help_buttons)
    try:
      btn = await self.bot.wait_for("button_click",timeout = 60 , check = lambda btn: btn.custom_id == "cmd" and btn.author == ctx.author)
    except:
      await help_msg.edit(components = inv_only_button)
    else: 
      await btn.edit_origin(components = inv_only_button)
      await self.command(ctx)
  
  @commands.command(aliases = ["cmd","cmds","commandlist"],description = "🗒 Display this message")
  async def command(self,ctx):
    await self.log.send(f"`{str(dt.now())[:-7]}` - {ctx.author} just used show command list command ;")
    final_list = f"**👍🏻 Few things to know before continue reading :**\n\n✅ *[argument] means it's required and <argument> means it's optional*\n✅ *You can mention {self.bot.user.mention} instead of a typing a prefix*"
    cogs = self.bot.cogs

    for cog_name in cogs:
      if "bot_admin" in cog_name or "event" in cog_name: continue
      final_list += f"\n\n**{cog_name.replace('_',' ').upper()}**\n"
      for command in cogs[cog_name].get_commands():
        name = command.name

        params = list(command.params.values())

        true_params = []
        for parm in params:
          parm = str(parm)
          if parm == "self" or parm == "ctx" or parm == "btnRequester": continue
          if "=None" in parm: 
            true_params.append(f"<{parm.replace('=None','')}>")
          else: true_params.append(f"[{parm}]")

        desc = f"```yaml\n{command.description}```"
        final_list += f"\n`{ctx.prefix}{name} {''.join(true_params)}`\n{desc}"

    cmd_embed = discord.Embed(
      title = "The command list of Music Can Weep",
      description = final_list,
      color = discord.Color.from_rgb(255,255,255)
    )

    channel = await ctx.author.create_dm()
    await channel.send(embed = cmd_embed)

  @commands.has_guild_permissions(administrator=True)
  @commands.command(aliases = ["sp","setprefix"],description = "⚙️ change my command prefix to whatever you want , maximum 3 characters \n( you will need to have administration permission in the server to use this command 🔣 )")
  async def set_prefix(self,ctx, *, new_prefix):
    await self.log.send(f"`{str(dt.now())[:-7]}` - {ctx.author} set my prefix in {ctx.guild} to `{new_prefix}` ;")

    if len(new_prefix) > 5: 
      return await ctx.reply("🚫 Prefix cannot be longer than 5 characters")

    db[str(ctx.guild.id)]["custom_prefix"] = new_prefix
    await ctx.reply(f"**✅ Successfully changed prefix to `{new_prefix}`**")
  
  @commands.command(aliases=["info"],description="📊 Display the live status of the bot")
  async def status(self,ctx):
    statusEmbed = discord.Embed(
      title = "**Current Status of the Bot**"
    )
    statusEmbed.add_field(
      name = "Servers",
      value = len(self.bot.guilds),
    )
    statusEmbed.add_field(
      name = "Voice Channel",
      value = len(self.bot.voice_clients),
    )
    statusEmbed.add_field(
      name = "Latency",
      value = f'{round(self.bot.latency * 1000)}ms',
    )

    guild = ctx.guild
    if guild:

      prefix = db[str(guild.id)].get("custom_prefix")

      statusEmbed.add_field(
        name = 'Server Prefix',
        value = f'`{prefix}`'
      )

      vc = ctx.voice_client

      statusEmbed.add_field(
        name = 'Server Voice Channel',
        value = f"`{vc.channel if vc else 'None'}`"
      )
      
    await ctx.reply(
      embed = statusEmbed
    )