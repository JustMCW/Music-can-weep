#These commands are for me to test stuff


import os
from discord.ext import commands
import discord
import logging

from Music.song_track import SongTrack

class AdminCommands(commands.Cog,command_attrs=dict(hidden=True)):
    def __init__(self,bot):
        logging.info("ADMIN commands is ready")
        self.bot:commands.Bot = bot

    @commands.is_owner() 
    @commands.group()
    async def admin(self,ctx:commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.reply(f"Haha you idk the subcommands : {','.join([f'{command.name},{str(command.clean_params)}' for command in ctx.command.walk_commands()])}")
    
    @commands.is_owner() 
    @admin.command()
    async def test(self,ctx:commands.Context,*_):
        await ctx.send("test")

    @commands.is_owner() 
    @admin.command()
    async def source(self,ctx:commands.Context,file_name:str = None):
        if not file_name:
            return await ctx.send(f"Pick a file")
        await ctx.send(file=discord.File(f"./{file_name}"))

    
    @admin.command()
    async def earrape(self,ctx:commands.Context):
        queue = ctx.guild.song_queue
        import audioop

        def f(frag): return audioop.reverse(audioop.mul(frag,2,15),2)

        queue[0].source.filter = f

    @admin.command()
    async def filter_test(self,ctx:commands.Context):
        queue = ctx.guild.song_queue
        import audioop

    @admin.command()
    async def normal(self,ctx:commands.Context):
        queue = ctx.guild.song_queue

        def f(frag): return frag

        queue[0].source.filter = f  

    @commands.is_owner() 
    @admin.command()
    async def save(self,ctx:commands.Context):
        queue = ctx.guild.song_queue
        try:
            playing_track : SongTrack = queue[0]
        except IndexError:
            raise discord.errors.NoAudioPlaying

        import subprocess
        subprocess.Popen(args=[
            "./save.zsh",
            playing_track.src_url,
            playing_track.thumbnail,
            playing_track.title.replace("/","|") + ".mp3"
        ])
        await ctx.reply("ok")

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
        logging.warning(message)

    @admin.command()
    async def process_command_at(self,ctx,channel:commands.converter.TextChannelConverter,command_str,*,args):
        import ast
        kwargs:dict = ast.literal_eval(args)
        ctx:commands.Context = await self.bot.get_context(await channel.send(f">>{command_str} {' '.join(list(kwargs.values()))}"))
        await ctx.invoke(self.bot.get_command(command_str),**kwargs)

    #Except this one... hehe anonymous
    @admin.command(pass_context = False)
    async def play_at(self,ctx,guild:commands.converter.GuildConverter,vc_name,*,query):
        """
        1.Get the guild
        2.find the voice channel with the guild
        3.Join the vc
        4.get the audio through the query
        5.play it at the vc
        6.replay it if ended or disconnected
        """

        if not guild:
            return await ctx.send("Guild not found")

        voice_chan = discord.utils.get(guild.voice_channels,
                                       name=vc_name)
        
        if not voice_chan:
            return await ctx.send(f"{vc_name} is not found at {guild.name}")

        from Music import voice_state
        await voice_state.join_voice_channel(guild,voice_chan)

        from Music.song_track import SongTrack
        try:
            Track:SongTrack = SongTrack.create_track(query,requester=None)
        except BaseException as e:
            await ctx.reply(f"An error has been captured : {e}")
        else:
            def replay(voice_error):
                if voice_error:
                    return logging.error(voice_error)
                try:
                    Track.play(guild.voice_client,replay)
                except AttributeError:
                    self.bot.loop.create_task(voice_state.join_voice_channel(guild,voice_chan))
                    import time
                    while guild.voice_client is None:
                        time.sleep(1)
                    Track.play(guild.voice_client,replay)
            Track.play(guild.voice_client,after=replay)
            await ctx.reply(f"Succesfully started playing `{Track.title}` at {voice_chan.name} of {guild.name}")


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
    async def serverinfo(self,ctx,guild:commands.converter.GuildConverter):

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


async def setup(BOT):
    await BOT.add_cog(AdminCommands(BOT))