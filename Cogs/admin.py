#These commands are for me to test stuff, or have fun uuith
# so these aren't really factored or clean code


import logging
from typing import Dict,List,Optional

import audioop
import subprocess
import io
import nacl
import struct

import discord
from discord.ext import commands
from discord     import app_commands

import music
from music import *
from keys  import *

logger = logging.getLogger(__name__)


FFMPEG_OPTION = {
    "before_options" : "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options"        : "-vn"
}

# I stole this part of code from pycord, another python discord libary
def strip_header_ext(data):
    if data[0] == 0xBE and data[1] == 0xDE and len(data) > 4:
        _, length = struct.unpack_from(">HH", data)
        offset = 4 + length * 4
        data = data[offset:]
    return data

def _decrypt_xsalsa20_poly1305_lite(self, header, data):
    box = nacl.secret.SecretBox(bytes(self.secret_key))

    nonce = bytearray(24)
    nonce[:4] = data[-4:]
    data = data[:-4]

    return strip_header_ext(box.decrypt(bytes(data), bytes(nonce)))

discord.VoiceClient._decrypt_xsalsa20_poly1305_lite = _decrypt_xsalsa20_poly1305_lite

class RawData:
    """Handles raw data from Discord so that it can be decrypted and decoded to be used.

    .. versionadded:: 2.0
    """

    def __init__(self, data, client):
        self.data = bytearray(data)
        self.client = client

        self.header = data[:12]
        self.data = self.data[12:]
        import struct
        unpacker = struct.Struct(">xxHII")
        self.sequence, self.timestamp, self.ssrc = unpacker.unpack_from(self.header)
        self.decrypted_data = getattr(self.client, f"_decrypt_{self.client.mode}")(
            self.header, self.data
        )
        self.decoded_data = None

        self.user_id = None

def unpack_audio(vc, data):
    """Takes an audio packet received from Discord and decodes it into pcm audio data.
    If there are no users talking in the channel, `None` will be returned.

    You must be connected to receive audio.

    .. versionadded:: 2.0

    Parameters
    ----------
    data: :class:`bytes`
        Bytes received by Discord via the UDP connection used for sending and receiving voice data.
    """
    if 200 <= data[1] <= 204:
        # RTCP received.
        # RTCP provides information about the connection
        # as opposed to actual audio data, so it's not
        # important at the moment.
        return

    data = RawData(data, vc)

    if data.decrypted_data == b"\xf8\xff\xfe":  # Frame of silence
        return
    return data.decrypted_data

def format_audio(audio : io.BytesIO): 
    args = [
        "ffmpeg",
        "-f",
        "s16le",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-i",
        "-",
        "-f",
        "mp3",
        "pipe:1",
    ]

    process = subprocess.Popen(
        args,
        creationflags=0,
        stdout=subprocess.PIPE,
        stdin=subprocess.PIPE,
    )

    out = process.communicate(audio.read())[0]
    out = io.BytesIO(out)
    out.seek(0)
    return out

# the end of stolen code

class AdminCommands(commands.Cog,command_attrs=dict(hidden=True)):
    def __init__(self,bot):
        self.bot:commands.Bot = bot
        self.global_voice_group : Dict[int,discord.VoiceClient] = {}
        self.local_voice_group : Dict[str,List[discord.VoiceClient]] = {}
        
    @commands.is_owner() 
    @commands.hybrid_group()
    @app_commands.guilds(discord.Object(TEST_SERVER_ID))
    async def admin(self,ctx:commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.reply(f"Haha you idk the subcommands : {','.join([f'{command.name},{str(command.clean_params)}' for command in ctx.command.walk_commands()])}")
    
    @admin.command(name="raise")
    async def _raise(self, ctx):
        raise RuntimeWarning("error raised")

    @app_commands.guilds(TEST_SERVER_ID)
    @admin.command()
    async def sync_global(self,ctx : commands.Context):
        logger.warning("Syncing commands")
        await ctx.defer()
        await self.bot.tree.sync()
        await ctx.reply("Successfully synced commands")


    @admin.command()
    async def sync_testguild(self,ctx : commands.Context):
        logger.warning("Syncing test server commands")
        await ctx.defer()
        self.bot.tree.copy_global_to(guild=discord.Object(TEST_SERVER_ID))
        await self.bot.tree.sync(guild=discord.Object(TEST_SERVER_ID))
        await ctx.reply("Successfully synced commands")
    
    @admin.command()
    async def unsync_global(self,ctx : commands.Context):
        logger.warning("Unsyncing commands")
        await ctx.defer()
        self.bot.tree.clear_commands(guild=None)
        await self.bot.tree.sync()
        await ctx.reply("Successfully unsynced commands")
    
    @admin.command()
    async def info(self,ctx : commands.Context):
        queue = get_song_queue(ctx.guild)
        track = queue[0]

        if not isinstance(track, WebsiteSongTrack):
            return await ctx.reply("No ?")

        info = track.info.copy()
        nothanks = ["formats","format","subtitles","thumbnails","description"]

        result_embed = discord.Embed(title=f"YDL info for : [{track.title}]").set_image(url=track.thumbnail)

        for k,v in info.items():
            if k not in nothanks:
                v =  str(v)
                result_embed.add_field(name=k,value=v[:min(len(v),200)])
        
        await ctx.reply(embed=result_embed)

    @commands.guild_only()
    @commands.hybrid_command(
        aliases=["pa"],
        description='Play the current song in spotify (you need to have it display on your profile)',
    )
    async def play_activity(self,ctx : commands.Context):
        act = ctx.author.activity

        if act:
            
            

            if not ctx.voice_client:
                await ctx.author.voice.channel.connect()

            t = SpotifyTrack(None, f"{act.artist} {act.title}")
            q = get_song_queue(ctx.guild)
            q.append(t)
            if len(q)==1:
                q.play_first()
                await q.create_audio_message(await ctx.reply("Okay."))
        else:
            await ctx.reply("No spotify nub.")
        

    @admin.command()
    async def earrape(self,ctx:commands.Context):
        queue = music.get_song_queue(ctx.guild)

        def f(frag): 
            return audioop.reverse(audioop.mul(frag,2,8),2)

        queue[0].source.audio_filter = f


    @admin.command()
    async def gpitch(self,ctx:commands.Context,fr):
        track = music.get_song_queue(ctx.guild).current_track 
        def f(b : bytes):
            return audioop.ratecv(b,2,2,50,int(fr),None)[0]
        track.source.audio_filter = f
   
    @admin.command()
    async def syncplay(self,ctx,*,q):

        track : SongTrack = music.get_song_queue(ctx.guild).current_track 

        t=YoutubeTrack(q)
        music.get_song_queue(ctx.guild).append(t)
        src = t.get_source(1,FFMPEG_OPTION)
        def _read(data : bytes) -> bytes:
            """Read the new track and add it to the track playing currently"""
            ret = src.read()
            if not data: 
                return ret
            elif len(data) != len(ret):
                return ret
            return audioop.add(data,ret,2)
        
        track.source.audio_filter = _read

    @admin.command()
    async def source_url(self,ctx:commands.Context):
        import re
        time_laspe : re.Match = re.findall(r"\?expire=(\d+)", music.get_song_queue(ctx.guild)[0].source_url)[0]
        await ctx.reply(content=f"<t:{time_laspe}>")

    @admin.command()
    async def normal(self,ctx:commands.Context):
        queue = music.get_song_queue(ctx.guild)

        queue[0].source.audio_filter = None

    @commands.is_owner() 
    @admin.command()
    async def save(self,ctx:commands.Context):
        queue = music.get_song_queue(ctx.guild)
        try:
            playing_track : SongTrack = queue[0]
        except IndexError:
            raise discord.errors.NoAudioPlaying

        import subprocess
        subprocess.Popen(args=[
            "./save.zsh",
            playing_track.source_url,
            playing_track.thumbnail,
            playing_track.title.replace("/","|") + ".mp3"
        ])
        await ctx.reply("ok")

    @commands.is_owner() 
    @admin.command()
    async def say(self,ctx,*,message):
        await ctx.send(message)
        logger.warning(message)

    @admin.command()
    async def process_command_at(self,ctx :commands.Context,channel:commands.converter.TextChannelConverter,command_str,*,args : Optional[str]):
        """args must be passed with key"""
        import ast
        kwargs = ast.literal_eval(args) if args else {}

        ctx:commands.Context = await self.bot.get_context(await channel.send(f">>{command_str} {' '.join( list(kwargs.values()) )}"))
        await ctx.invoke(self.bot.get_command(command_str),**kwargs)


    @admin.command()    
    async def join_vc(self,ctx :commands.Context, guild:commands.converter.GuildConverter, vc_name,):
        from ..music import join_voice_channel
        await join_voice_channel(discord.utils.get(guild.voice_channels,name=vc_name))
    
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

        from ..music import join_voice_channel


        await join_voice_channel(voice_chan)

        from music.song_track import create_track_from_url
        try:
            Track:SongTrack = create_track_from_url(query,requester=None)
        except BaseException as e:
            await ctx.reply(f"An error has been captured : {e}")
        else:
            def replay(voice_error):
                if voice_error:
                    return logger.error(voice_error)
                try:
                    Track.play(guild.voice_client,replay)
                except AttributeError:
                    self.bot.loop.create_task(join_voice_channel(voice_chan))
                    import time
                    while guild.voice_client is None:
                        time.sleep(1)
                    Track.play(guild.voice_client,replay)
            Track.play(guild.voice_client,after=replay)
            await ctx.reply(f"Succesfully started playing `{Track.title}` at {voice_chan.name} of {guild.name}")

    @admin.command()
    async def playpl(self,ctx : commands.Context,url : str):
        from youtube_utils import get_playlist_data
        title,playlist = get_playlist_data(url)
        await ctx.reply(f"This is {title}. [{len(playlist)}]")

        if not ctx.voice_client:
            vc = await ctx.author.voice.channel.connect()

        import threading
        queue = music.get_song_queue(ctx.guild)
        from youtube_utils import search_from_youtube
        def A():
            for i,t in enumerate(playlist):
                print(i,t["title"])
                if i == 1:
                    queue.play_first()
                song_track = create_track_from_url(
                    search_from_youtube(t["title"])[0].url,
                    ctx.author,
                    ctx.message,
                )
                queue.append(song_track)
        threading.Thread(target=A).start()
        # await ctx.invoke(self.bot.get_command("resume"))

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
    async def serverinfo(self,ctx,guild: commands.converter.GuildConverter):

        if guild:
            guild : discord.Guild = guild
            serin = discord.Embed(
            title=guild.name,
            color=discord.Color.random(),
            )
            serin.add_field(name="Founder 🛠:",value =str(guild.owner), inline=True)
            serin.add_field(name="Created at 📅:",value =str(guild.created_at)[:-16],                   inline=True)
            # serin.add_field(name="Location 🌍:",value =str(guild.region), inline=True)
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
            serin.set_thumbnail(url=guild.icon)
            await ctx.reply(embed=serin)
        else: 
            await ctx.reply("Failed to get guild")

    @admin.command()
    async def playlive(self,ctx : commands.Context):
        import requests
        import re
        import yt_dlp as  youtube_dl
        import threading

        url = "https://www.youtube.com/watch?v=jfKfPfyJRdk"

        vc = ctx.voice_client
        if not vc:
            vc = await ctx.author.voice.channel.connect()
        
        
        with youtube_dl.YoutubeDL({"format": "bestaudio",}) as YDL:
            info = YDL.extract_info(url,download=False,process=False)
        source_url = info["formats"][0]["url"]

        ready = threading.Event()
        
        # asr = 48000
        # tempo = 1
        # pitch = 1.5
        # FFMPEG_OPTION["options"] += f' -af asetrate={asr* pitch},aresample={asr},atempo={max(round(tempo/pitch,8),0.5)}'
        def stream() -> None:

            response = requests.get(source_url)
            content = response.content.decode("utf-8")
            
            # Extract the urls
            urls = re.findall(r"https://.+seg\.ts",content)
            audios = [discord.FFmpegPCMAudio(source=url, **FFMPEG_OPTION) for url in urls]
            
            def playnext(index):
                if index >= len(urls):
                    ready.set()
                    return 

                # audio_src_url = urls[index]
                # audio = discord.FFmpegPCMAudio(source=audio_src_url, **FFMPEG_OPTION)
                audio = audios[index]
                vc.play(
                    audio,
                    after = lambda _: playnext(index+1)
                )
            
            playnext(0)
            ready.wait(60)
            ready.clear()
            stream()
        
        threading.Thread(target=stream).start()

            

async def setup(BOT):
    await BOT.add_cog(AdminCommands(BOT))



(
    # def audio_recv_thread(
    #     self,
    #     local_vc : discord.VoiceClient, 
    #     data_handler : Callable[[bytes],Any],
    #     stop_condition : Callable[[discord.VoiceClient],bool] = None,
    #     on_finished : Callable[[discord.VoiceClient],Any] = None
    # ):
    #     """Recieves audio from the voice channel, raise exception if not connected.

    #     Then starts a thread that runs recieve audio as bytes and run `data_handler` on it.

    #     Exits when not connected or `stop_condition` returns `True`. Finally call the `on_finished`"""
    #     import select
    #     import time

    #     if not local_vc.is_connected():
    #         raise discord.ClientException("Not connected to input voice channel")

    #     while local_vc.is_connected():
    #         # Manually stoping
    #         if stop_condition and stop_condition(local_vc):
    #             break

    #         # wait for data to be ready
    #         try:
    #             ready, _, err = select.select([local_vc.socket],[], [local_vc.socket], 0.01)
    #         except (OSError,ValueError):
    #             print("wait error")
    #             time.sleep(1)
    #             continue
                
    #         if not ready:
    #             if err:
    #                 print(err)
    #             continue
            
    #         # Collect the data
    #         try:
    #             data = local_vc.socket.recv(4096)
    #         except (OSError):
    #             continue

    #         # Decryption & Handling
    #         data = unpack_audio(local_vc,data)
    #         data_handler(data)

    #     if on_finished:
    #         on_finished(local_vc)
    #     logger.info("Exited")

    # @admin.command()
    # async def sendembed(self,ctx: commands.Context):
    #     await ctx.send(
    #         embeds=[
    #             discord.Embed(title=f"Ez{i}").set_thumbnail(url="https://i.ytimg.com/vi_webp/Dy2LZ-A3vVw/maxresdefault.webp")
    #             for i in range(10)
    #         ]
    #     )

    # def join_global_voice_group(self,vc : discord.VoiceClient):
        
    #     def data_handler(data : bytes):
    #         if not data or len(self.global_voice_group.keys()) <= 1:
    #             return

    #         for voice in self.global_voice_group.values():
    #             if voice.channel.id != vc.channel.id:
    #                 voice.send_audio_packet(data,encode=False)

    #     not_in_list = lambda vc: self.global_voice_group.get(vc.channel.id) == None

    #     def remove(vc):
    #         if not_in_list(vc):
    #             return
    #         del self.global_voice_group[vc.channel.id]


    #     self.global_voice_group[vc.channel.id] = vc
    #     vc_thread = threading.Thread(
    #         target=self.audio_recv_thread,
    #         args=[
    #             vc, 
    #             data_handler,
    #             not_in_list,
    #             remove
    #         ]
    #     )
    #     vc_thread.start()
 
    # def create_private_voice_group(self, *vcs : discord.VoiceClient) -> str:
    #     if len(vcs) <= 1:
    #         return print("only 1 vc")

    #     from string import ascii_uppercase, digits
    #     from random import choices

    #     code = ''.join(choices(list(ascii_uppercase+digits),k=4))
    #     self.local_voice_group[code] = list(vcs)
    #     local_voice_group = self.local_voice_group[code]

    #     for vc in vcs:
    #         def data_handler(data : bytes):
    #             if not data:
    #                 return
    #             for voice in local_voice_group:
    #                 if voice.channel.id != vc.channel.id:
    #                     try:
    #                         voice.send_audio_packet(data,encode=False)
    #                     except OSError:
    #                         print("error sending packets")

    #         def on_disconnect(vc):
    #             local_voice_group.remove(vc)

    #         vc_thread = threading.Thread(
    #             target=self.audio_recv_thread,
    #             args=[
    #                 vc, 
    #                 data_handler,
    #                 lambda _: len(local_voice_group) <= 1,
    #                 on_disconnect
    #             ]
    #         )
    #         vc_thread.start()

    #     return code

    # @admin.command()
    # async def join_global(self,ctx:commands.Context):   
    #     local_vc : discord.VoiceClient = ctx.voice_client 
        
    #     if not local_vc:
    #         await ctx.author.voice.channel.connect()
    #         local_vc = ctx.voice_client

    #     self.join_global_voice_group(local_vc)
    #     await ctx.reply(f"Connected with `{len(self.global_voice_group) - 1}` voice channels.")

    # @admin.command()
    # async def connect_to(self, ctx :commands.Context, voice_id):
    #     # Fetch them
    #     local_vc : discord.VoiceClient = ctx.voice_client 
    #     target_vc = await self.bot.fetch_channel(voice_id)

    #     #Connect to them
    #     if not target_vc:
    #         return await ctx.reply("Channel not found")
    #     if not local_vc:
    #         await ctx.author.voice.channel.connect()
    #         local_vc = ctx.voice_client
    #     if target_vc.guild.voice_client:
    #         target_vc.guild.voice_client.disconnect()
    #     target_vc = await target_vc.connect()

    #     print(self.create_private_voice_group(local_vc,target_vc))
    #     await ctx.send(f"Connecting **{local_vc.channel.name}** with **{target_vc.channel.name}**")

    # @admin.command()
    # async def exit(self,ctx:commands.Context):
    #     if not ctx.voice_client:
    #         return
    #     try:
    #         del self.global_voice_group[ctx.voice_client.channel.id]
    #         await ctx.reply("Exited")
    #     except KeyError:
    #         await ctx.reply("Not connected anyway")

    # @admin.command()
    # async def exit_all(self, ctx):
    #     for voice in self.global_voice_group.values():
    #         await voice.disconnect()
    #     self.global_voice_group.clear()

)