import discord
from discord    import ButtonStyle,Interaction
from discord.ui import View,Button,Modal,TextInput, button

discord.Guild
from string_literals import MessageString,MyEmojis
from Music           import voice_state
from Music.song_queue import VOLUME_PERCENTAGE_LIMIT,SongQueue

import Convert

async def inform_changes(interaction : Interaction,message:str):
    if len(voice_state.get_non_bot_vc_members(interaction.guild)) > 1:
        return await interaction.response.send_message(content=f"{message} by {interaction.user.display_name}")
    try:
        await interaction.response.defer()
    except (discord.errors.HTTPException,discord.errors.InteractionResponded): 
        pass

#BUTTONS
class MusicButtons:

    class QueueButtons(View):
        @button(style=ButtonStyle.grey,emoji="🗑")
        async def on_clear(self,interaction:Interaction,btn):
            await inform_changes(interaction,"Queue has been cleared")
            interaction.guild.song_queue.cleanup()

    class AudioControllerButtons(View):
        """Contains all the buttons needed for the audio control message"""
        
        def __init__(self, queue : SongQueue):
            super().__init__(timeout=None) #Disables timeout
            self.on_displayqueue.disabled = not queue.enabled
            self.on_previous.disabled = not bool(queue.history) and not queue.queue_looping
            self.on_rewind.disabled = not queue[0].seekable
            self.on_nextrec.disabled = not queue.auto_play or queue.get(1)

        ### Row 0
        @button(style=ButtonStyle.grey,emoji=MyEmojis.previous,row=0)
        async def on_previous(self, interaction:Interaction, btn : Button):
            
            guild = interaction.guild
            queue = guild.song_queue
            if queue.queue_looping:
                voice_state.shift_track(guild,-1)
            else:
                if not interaction.guild.song_queue.history:
                    return await interaction.response.send_message(ephemeral=True,content="No track was played before this.")
                voice_state.rewind_track(guild)
        
            await inform_changes(interaction,MessageString.rewind_audio_msg)

        @button(style=ButtonStyle.grey,emoji=MyEmojis.rewind,row=0)
        async def on_rewind(self, interaction:Interaction, btn : Button):
            interaction.guild.song_queue.time_position -= 5
            await inform_changes(interaction,"Rewinded for 5 seconds")

        @button(style=ButtonStyle.grey,emoji=MyEmojis.pause,row=0)
        async def on_playpause(self, interaction:Interaction, btn : Button):
            is_paused = voice_state.is_paused(interaction.guild)
            if is_paused:
                voice_state.resume_audio(interaction.guild)
            else:
                voice_state.pause_audio(interaction.guild)

            await inform_changes(interaction, MessageString.paused_audio_msg if not is_paused else MessageString.resumed_audio_msg)
            
            btn.emoji = MyEmojis.pause if is_paused else MyEmojis.resume
            await interaction.message.edit(view=self)

        @button(style=ButtonStyle.grey,emoji=MyEmojis.fastforward,row=0)
        async def on_forword(self, interaction:Interaction, btn : Button):
            interaction.guild.song_queue.time_position += 5
            await inform_changes(interaction,"Fast-forwarded for 5 seconds")
    
        @button(style=ButtonStyle.grey,emoji=MyEmojis.skip,row=0)
        async def on_skip(self, interaction:Interaction, btn : Button):
            guild = interaction.guild
            queue = guild.song_queue
            if queue.queue_looping:
                voice_state.shift_track(guild)
            else:
                voice_state.skip_track(guild)
            await inform_changes(interaction,MessageString.skipped_audio_msg)


        ###Row 1
        @button(style=ButtonStyle.grey,emoji=MyEmojis.download,row=1)
        async def on_download(self, interaction:Interaction, btn : Button):
            import subprocess,io,asyncio,threading,time
            event_loop = asyncio.get_running_loop()
            await interaction.response.send_message(ephemeral=True,content="Processing ...")
            track = interaction.guild.song_queue[0]
            asr = track.audio_asr
            track_bytes = io.BytesIO()
            
            def inter():
                process = subprocess.Popen(
                    args=["ffmpeg","-i",f"{track.src_url}",
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
                event_loop.create_task(interaction.followup.send(file=file))
                track_bytes.close()
            t = threading.Thread(target=inter)
            t.start()
            """
            ['ffmpeg', '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5', '-i', 
            'https://rr10---sn-cu-auos.googlevideo.com/videoplayback?expire=1664952609&ei=wdQ8Y_n7DMijW7yMmIgJ&ip=86.186.177.136&id=o-ALGvImbiYsU-t68wfnIYVT4LT6JlKga7rRwWpQuDP6L6&itag=249&source=youtube&requiressl=yes&mh=E7&mm=31%2C26&mn=sn-cu-auos%2Csn-5hne6nzd&ms=au%2Conr&mv=m&mvi=10&pl=25&pcm2=yes&initcwndbps=1901250&vprv=1&mime=audio%2Fwebm&ns=8DaPVtaCB4UCfJQYocp0gjwI&gir=yes&clen=497483&dur=81.541&lmt=1589626985412866&mt=1664930702&fvip=4&keepalive=yes&fexp=24001373%2C24007246&c=WEB&txp=6311222&n=66glphtnoGQZ3rQa&sparams=expire%2Cei%2Cip%2Cid%2Citag%2Csource%2Crequiressl%2Cpcm2%2Cvprv%2Cmime%2Cns%2Cgir%2Cclen%2Cdur%2Clmt&sig=AOq0QJ8wRQIgTuTQYEYNxD3waFEpCxb0HeFbNzbXyCCYHT2atps0Jq8CIQCyB2nJOUKNtFpsfQEZTLWpcNGCxpe7BcSUtGvcfkT34Q%3D%3D&lsparams=mh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Cinitcwndbps&lsig=AG3C_xAwRQIhAKCqpGUbS7bz5uqgJJwWFOhzFQTWzWimW9Zczy4WHEeGAiApDurPO8iI6IV7Q2Pq6y8bKO1982Q_ZqctJorYwP7jhA%3D%3D', 
            '-f', 's16le', '-ar', '48000', '-ac', '2', '-loglevel', 'warning', '-vn', '-af', 'asetrate=48000,aresample=48000,atempo=1.0', 'pipe:1']
            """
            

        @button(style=ButtonStyle.grey,emoji=MyEmojis.queue,row=1)
        async def on_displayqueue(self, interaction:Interaction, btn : Button):
            import datetime
            queue = interaction.guild.song_queue
            emo = "▶︎" if not voice_state.is_paused(interaction.guild) else "\\⏸"
            await interaction.response.send_message(ephemeral=True,
                embed=discord.Embed(title = f"🎧 Queue | Track Count : {len(queue)} | Full Length : {convert.length_format(queue.total_length)} | Repeat queue : {convert.bool_to_str(queue.queue_looping)}",
                                            #                           **   [Index] if is 1st track [Playing Sign]**    title   (newline)             `Length`               |         @Requester         Do this for every track in the queue
                                            description = "\n".join([f"**{f'[ {i} ]' if i > 0 else f'[{emo}]'}** {track.title}\n> `{convert.length_format(track.duration)}` | {track.requester.display_name}" for i,track in enumerate(list(queue))]),
                                            color=discord.Color.from_rgb(255, 255, 255),
                                            timestamp=datetime.datetime.now()),
                view=MusicButtons.QueueButtons()
            )

        @button(style=ButtonStyle.grey,emoji=MyEmojis.singleloop,row=1)
        async def on_singleloop(self, interaction:Interaction, btn : Button):
            queue = interaction.guild.song_queue
            queue.looping = not queue.looping
            await queue.update_audio_message()
            await inform_changes(interaction,MessageString.loop_audio_msg.format(convert.bool_to_str(queue.looping)))
        
        @button(style=ButtonStyle.grey,emoji=MyEmojis.config,row=1)
        async def on_config(self, interaction:Interaction, btn : Button):

            class ConfigModal(Modal,title = "Configuration of the audio"):
                volume_space = TextInput(label='Volume', style=discord.TextStyle.short,placeholder="1-200%",max_length=3,required=False)
                tempo_space = TextInput(label='Tempo', style=discord.TextStyle.short,placeholder="0.5-2.5",max_length=5,required=False)
                pitch_space = TextInput(label='Pitch', style=discord.TextStyle.short,placeholder="0.5-2.5",max_length=5,required=False)
                
                async def on_submit(_self, interaction: Interaction) -> None:

                    guild = interaction.guild

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
                            if volume_percentage > VOLUME_PERCENTAGE_LIMIT and interaction.user.id != self.bot.owner_id:
                                return await interaction.response.send_message(f"🚫 Please enter a volume below {VOLUME_PERCENTAGE_LIMIT}% (to protect yours and other's ears 👍🏻)",ephemeral=True)
                            else:
                                vol_changed = not vol_changed
                                #Updating to the new value
                                guild.song_queue.volume_percentage = volume_percentage

                    if new_tempo:

                        try:
                            new_tempo = float(new_tempo)
                            if new_tempo <= 0:
                                voice_state.pause_audio(guild)
                                return await interaction.reply(MessageString.paused_audio_msg)
                            elif new_tempo < 0.5 or new_tempo > 5:
                                return await interaction.response.send_message("Tempo can only range between `0.5-5`.",ephemeral=True)

                        except ValueError:
                            return await interaction.response.send_message("Invalid tempo.",ephemeral=True)
                        else:
                            guild.song_queue.tempo = new_tempo
                            tempo_changed = not tempo_changed

                    if new_pitch:
                        queue = guild.song_queue
                        
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

                    await queue.update_audio_message()
                    if pitch_changed or tempo_changed:
                        if guild.voice_client and guild.voice_client._player and guild.song_queue:
                            voice_state.replay_track(guild)

                    await inform_changes(interaction,"New configuration of the audio set")

            await interaction.response.send_modal(ConfigModal())
        
        
        @button(style=ButtonStyle.grey,emoji="↪️",row=1)
        async def on_nextrec(self, interaction:Interaction, btn : Button):
            guild = interaction.guild
            queue = guild.song_queue

            if not queue.auto_play:
                return await interaction.response.send_message(ephemeral=True,content="This button changes the next track played by auto-play, however auto-play is currently off, turn it on with \"queue autoplay on\"")
            elif queue.queue_looping:
                return await interaction.response.send_message(ephemeral=True,content="This button changes the next track played by auto-play, however auto-play can never be reached when queue looping is on, turn it off with \"queue loop off\"")
            await interaction.response.defer()
            queue._recommendations.rotate(-1)
            await queue.update_audio_message()


    @staticmethod
    async def on_play_again_btn_press(btn,bot):
        ctx = await bot.get_context(btn.message)

        URL = btn.message.embeds[0].url

        #Play the music
        await ctx.invoke(bot.get_command('play'),
                         query=URL,
                         _btn=btn)


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