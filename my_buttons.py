import discord
from discord    import ButtonStyle,Interaction
from discord.ui import View,Button,Modal,TextInput, button
from discord.ext import commands

from typing   import TYPE_CHECKING
from literals import ReplyStrings,MyEmojis

import music
from music    import voice_utils

if TYPE_CHECKING:
    from music import SongQueue

from typechecking import *


import convert
import database.user_playlist as playlistdb
from music.voice_constants import *

ROW1_COLOUR = ButtonStyle.gray

async def inform_changes(
    interaction : Interaction,
    message     :str
):
    """Notify other users for the changes, such as pausing, skipping."""

    try:
        await interaction.response.defer()
    except (discord.errors.HTTPException,discord.errors.InteractionResponded): 
        pass
    if len(voice_utils.voice_members(interaction.guild)) > 1:
        return await interaction.channel.send(content=f"{message} by {interaction.user.display_name}",delete_after=30)


class ConfigModal(Modal,title = "Configuration of the audio"):
    volume_space = TextInput(label='Volume', style=discord.TextStyle.short,placeholder="1-200%",max_length=3,required=False)
    tempo_space = TextInput(label='Tempo', style=discord.TextStyle.short,placeholder="0.5-2.5",max_length=5,required=False)
    pitch_space = TextInput(label='Pitch', style=discord.TextStyle.short,placeholder="0.5-2.5",max_length=5,required=False)
    
    async def on_submit(_self, interaction: Interaction) -> None:

        guild= interaction.guild
        queue = music.get_song_queue(guild)

        vol_changed,tempo_changed,pitch_changed = False,False,False

        volume_to_set = str(_self.volume_space)
        new_tempo = str(_self.tempo_space)
        new_pitch = str(_self.pitch_space)

        #The anoyying part, jusst ignore it.
        if volume_to_set:

            try: volume_percentage = convert.extract_int_from_str(volume_to_set)
            except ValueError: ...
            else:
                #Volume higher than the limit
                if volume_percentage > MAX_VOLUME_PERCENTAGE and interaction.user.id != self.bot.owner_id:
                    return await interaction.response.send_message(f"🚫 Please enter a volume below {MAX_VOLUME_PERCENTAGE}% (to protect yours and other's ears 👍🏻)",ephemeral=True)
                else:
                    vol_changed = not vol_changed
                    #Updating to the new value
                    music.get_song_queue(guild).volume_percentage = volume_percentage

        if new_tempo:

            try:
                new_tempo = float(new_tempo)
                if new_tempo <= 0:
                    voice_utils.pause_audio(guild)
                    return await interaction.reply(ReplyStrings.PAUSE)
                elif new_tempo < 0.5 or new_tempo > 5:
                    return await interaction.response.send_message("Tempo can only range between `0.5-5`.",ephemeral=True)

            except ValueError:
                return await interaction.response.send_message("Invalid tempo.",ephemeral=True)
            else:
                music.get_song_queue(guild).tempo = new_tempo
                tempo_changed = not tempo_changed

        if new_pitch:
            
            try:
                if float(new_pitch) <= 0:
                    raise ValueError
                #tempo / pitch >= 0.5
            except ValueError:
                return  await interaction.response.send_message("Invalid pitch.",ephemeral=True)
            else:
                queue.pitch = float(new_pitch)
                pitch_changed = not pitch_changed


        #Applying it
        
        #Nothing changed
        if not (vol_changed or tempo_changed or pitch_changed):
            return await interaction.response.defer()

        await music.update_audio_message(queue)
        if pitch_changed or tempo_changed:
            if guild.voice_client and guild.voice_client._player and music.get_song_queue(guild):
                queue.replay_track()

        await inform_changes(interaction,"New configuration of the audio set")

#BUTTONS
class MusicButtons:

    class QueueButtons(View):
        @button(style=ButtonStyle.grey,emoji="🗑")
        async def on_clear(self,interaction:Interaction,btn):
            await inform_changes(interaction,"Queue has been cleared")
            await music.get_song_queue(interaction.guild).cleanup()

    class AudioControllerButtons(View):
        """Contains all the buttons needed for the audio control message"""
        
        def __init__(self, queue : 'SongQueue' = None):
            super().__init__(timeout=None)
            if not queue:
                return 

            playing_track = queue.current_track
            #Disabling buttons
            # self.on_displayqueue.disabled = not queue.enabled
            self.on_previous.disabled = not bool(queue.history) and not queue.queue_looping
            if playing_track:
                self.on_rewind.disabled = not playing_track.seekable
            # self.on_forword.disabled = self.on_download.disabled = self.on_trackloop.disabled = self.on_config.disabled = queue[0].is_livestream
            # self.on_nextrec.disabled = not queue.auto_play or queue.get(1)

        ### Row 1
        @button(style=ROW1_COLOUR,emoji=MyEmojis.PREVIOUS,row=0,custom_id="previous")
        async def on_previous(self, interaction:Interaction, btn : Button):
            
            guild= interaction.guild
            queue = music.get_song_queue(guild)
            if queue.queue_looping:
                queue.shift_track(-1)
            else:
                if not queue.history:
                    return await interaction.response.send_message(ephemeral=True,content="No track was played before this.")
                queue.rewind_track()
        
            await inform_changes(interaction,ReplyStrings.REWIND)

        @button(style=ROW1_COLOUR,emoji=MyEmojis.REWIND,row=0,custom_id="rewind")
        async def on_rewind(self, interaction:Interaction, btn : Button):
            queue = music.get_song_queue(interaction.guild)
            queue.time_position -= 5
            await inform_changes(interaction,"Rewinded for 5 seconds")

        @button(style=ROW1_COLOUR,emoji=MyEmojis.PAUSE,row=0,custom_id="playpause")
        async def on_playpause(self, interaction:Interaction, btn : Button):
            guild = interaction.guild
            is_paused = voice_utils.is_paused(guild)
            if is_paused:
                voice_utils.resume_audio(guild)
            else:
                voice_utils.pause_audio(guild)

            await inform_changes(interaction, ReplyStrings.PAUSE if not is_paused else ReplyStrings.RESUME)
            
            btn.emoji = MyEmojis.PAUSE if is_paused else MyEmojis.RESUME
            await interaction.message.edit(view=self)

        @button(style=ROW1_COLOUR,emoji=MyEmojis.FASTFORWARD,row=0,custom_id="forward")
        async def on_forword(self, interaction:Interaction, btn : Button):
            queue = music.get_song_queue(interaction.guild)
            queue.time_position += 5
            await inform_changes(interaction,"Fast-forwarded for 5 seconds")
    
        @button(style=ROW1_COLOUR,emoji=MyEmojis.SKIP,row=0,custom_id="skip")
        async def on_skip(self, interaction:Interaction, btn : Button):
            queue = music.get_song_queue(interaction.guild)
            if queue.queue_looping:
                queue.shift_track()
            else:
                queue.skip_track()
            await inform_changes(interaction,ReplyStrings.SKIP)

        ###Row 2
        @button(style=ButtonStyle.red,emoji=MyEmojis.FAVOURITE,row=1,custom_id="favourite")
        async def on_favourite(self, interaction:Interaction, btn : Button):
            queue = music.get_song_queue(interaction.guild)
            track = queue.current_track

            if not track:
                raise RuntimeError("Favouriting no track?")
            
            playlistdb.add_track(
                interaction.user,
                [track],
            )
            await interaction.response.send_message(
                ephemeral=True,
                content=f"Track ***{track.title}*** has been added to your favourite."
            )

        @button(style=ButtonStyle.grey,emoji=MyEmojis.DOWNLOAD,row=1,custom_id="download")
        async def on_download(self, interaction:Interaction, btn : Button):
            import subprocess
            import io
            import asyncio
            import threading
            import time

            event_loop = asyncio.get_running_loop()

            await interaction.response.send_message(
                ephemeral=True,
                content="Processing ..."
            )
            queue = music.get_song_queue(interaction.guild)
            track = queue.current_track

            if not track:
                raise RuntimeError("No track to be downloaded")


            asr = track.sample_rate
            track_bytes = io.BytesIO()
            
            def inter():
                process = subprocess.Popen(
                    args=["ffmpeg","-i",f"{track.source_url}",
                    '-f', 'mp3', '-ar', '48000', '-ac', '2', '-loglevel', 'warning', '-vn', '-af', f'asetrate={asr},aresample={asr},atempo=1.0', 'pipe:1'],
                                        stdin=-3,
                                        stdout=subprocess.PIPE,#{'stdout': -1, 'stdin': -3, 'stderr': None}
                                        stderr=None)
                while True:
                    data = process.stdout.read()
                    if not data: break
                    track_bytes.seek(0,io.SEEK_END)
                    track_bytes.write(data)
                    time.sleep(1)
                track_bytes.seek(0)
                file = discord.File(track_bytes)
                file.filename = "music.mp3"
                event_loop.create_task(interaction.channel.send(file=file))
                track_bytes.close()
            t = threading.Thread(target=inter)
            t.start()
            """
            ['ffmpeg', '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5', '-i', 
            'https://rr10---sn-cu-auos.googlevideo.com/videoplayback?expire=1664952609&ei=wdQ8Y_n7DMijW7yMmIgJ&ip=86.186.177.136&id=o-ALGvImbiYsU-t68wfnIYVT4LT6JlKga7rRwWpQuDP6L6&itag=249&source=youtube&requiressl=yes&mh=E7&mm=31%2C26&mn=sn-cu-auos%2Csn-5hne6nzd&ms=au%2Conr&mv=m&mvi=10&pl=25&pcm2=yes&initcwndbps=1901250&vprv=1&mime=audio%2Fwebm&ns=8DaPVtaCB4UCfJQYocp0gjwI&gir=yes&clen=497483&dur=81.541&lmt=1589626985412866&mt=1664930702&fvip=4&keepalive=yes&fexp=24001373%2C24007246&c=WEB&txp=6311222&n=66glphtnoGQZ3rQa&sparams=expire%2Cei%2Cip%2Cid%2Citag%2Csource%2Crequiressl%2Cpcm2%2Cvprv%2Cmime%2Cns%2Cgir%2Cclen%2Cdur%2Clmt&sig=AOq0QJ8wRQIgTuTQYEYNxD3waFEpCxb0HeFbNzbXyCCYHT2atps0Jq8CIQCyB2nJOUKNtFpsfQEZTLWpcNGCxpe7BcSUtGvcfkT34Q%3D%3D&lsparams=mh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Cinitcwndbps&lsig=AG3C_xAwRQIhAKCqpGUbS7bz5uqgJJwWFOhzFQTWzWimW9Zczy4WHEeGAiApDurPO8iI6IV7Q2Pq6y8bKO1982Q_ZqctJorYwP7jhA%3D%3D', 
            '-f', 's16le', '-ar', '48000', '-ac', '2', '-loglevel', 'warning', '-vn', '-af', 'asetrate=48000,aresample=48000,atempo=1.0', 'pipe:1']
            """
            

        # @button(style=ButtonStyle.grey,emoji=MyEmojis.QUEUE,row=1, custom_id="queue")
        # async def on_displayqueue(self, interaction:Interaction, btn : Button):
        #     import datetime
        #     queue = interaction.music.get_song_queue
        #     emo = "▶︎" if not voice_state.is_paused(interaction.guild) else "\\⏸"
        #     await interaction.response.send_message(ephemeral=True,
        #         embed=discord.Embed(title = f"🎧 Queue | Track Count : {len(queue)} | Full Length : {convert.length_format(queue.total_length)} | Repeat queue : {ReplyStrings.prettify_bool(queue.queue_looping)}",
        #                                     #                           **   [Index] if is 1st track [Playing Sign]**    title   (newline)             `Length`               |         @Requester         Do this for every track in the queue
        #                                     description = "\n".join([f"**{f'[ {i} ]' if i > 0 else f'[{emo}]'}** {track.title}\n> `{convert.length_format(track.duration)}` | {track.requester.display_name}" for i,track in enumerate(list(queue))]),
        #                                     color=discord.Color.from_rgb(255, 255, 255),
        #                                     timestamp=datetime.datetime.now()),
        #         view=MusicButtons.QueueButtons()
        #     )

        @button(style=ButtonStyle.grey,emoji=MyEmojis.TRACKLOOP,row=1,custom_id="loop")
        async def on_trackloop(self, interaction:Interaction, btn : Button):
            guild = ensure_exist(interaction.guild)
            queue = music.get_song_queue(guild)
            queue.looping = not queue.looping

            await inform_changes(interaction,ReplyStrings.TRACK_LOOP(queue.looping))
            await music.update_audio_message(queue)
        
        @button(style=ButtonStyle.grey,emoji=MyEmojis.QUEUELOOP,row=1,custom_id="queueloop")
        async def on_queueloop(self, interaction:Interaction, btn : Button):
            guild= ensure_exist(interaction.guild)
            queue = music.get_song_queue(guild)
            queue.queue_looping = not queue.queue_looping

            await inform_changes(interaction,ReplyStrings.QUEUE_LOOP(queue.queue_looping))
            await music.update_audio_message(queue)
        
        @button(style=ButtonStyle.grey,emoji=MyEmojis.CONFIG,row=1,custom_id="config")
        async def on_config(self, interaction:Interaction, btn : Button):

            await interaction.response.send_modal(ConfigModal())
        
        
        # @button(style=ButtonStyle.grey,emoji="↪️",row=1)
        # async def on_nextrec(self, interaction:Interaction, btn : Button):
        #     guild = interaction.guild
        #     queue = music.get_song_queue

        #     if not queue.auto_play:
        #         return await interaction.response.send_message(ephemeral=True,content="This button changes the next track played by auto-play, however auto-play is currently off, turn it on with \"queue autoplay on\"")
        #     elif queue.queue_looping:
        #         return await interaction.response.send_message(ephemeral=True,content="This button changes the next track played by auto-play, however auto-play can never be reached when queue looping is on, turn it off with \"queue loop off\"")
        #     await interaction.response.defer()
        #     queue[0].recommendations.rotate(-1)
        #     await music.update_audio_message(queue)


    @staticmethod
    async def on_play_again_btn_press(btn : discord.Interaction,bot : commands.Bot):
        ctx = await bot.get_context(ensure_exist(btn.message))

        if not ctx.voice_client and not btn.user.voice:
            return await btn.response.send_message(
                ephemeral=True,
                content=ReplyStrings.user_not_in_vc_msg
            )
        await btn.response.defer()
        from cogs.play import play_track_handler

        URL = btn.message.embeds[0].url
        await play_track_handler(ctx,URL, await ctx.reply(f"{btn.user.display_name} plays this again ~"),author=btn.user)

    PlayAgainButton = View().add_item(
        Button(label="Replay this song !",
                custom_id="play_again",
                style=ButtonStyle.primary,
                emoji="🎧")
    )


class UtilityButtons(View):
    @discord.ui.button(emoji="♻️",custom_id="delete",style=ButtonStyle.blurple)
    async def delete_button(self,interaction : Interaction,btn):
        pass

CONTROLLER_IDS = []

if not CONTROLLER_IDS:
    for row in MusicButtons.AudioControllerButtons().to_components():
        CONTROLLER_IDS.extend(
            [item["custom_id"] for item in row["components"]]
        )
