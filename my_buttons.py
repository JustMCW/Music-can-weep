from tkinter.tix import ButtonBox
import discord
from discord    import ButtonStyle,Interaction
from discord.ui import View,Button,Modal,TextInput

from string_literals import MessageString
from Music           import voice_state
import convert

#BUTTONS
class MusicButtons:
    
    #Button Templates
    PlayPauseButton = Button(#label="Pause",
                          custom_id="playpause",
                          style=ButtonStyle.grey,
                          emoji="⏸") #Default playing
    SkipButton = Button(#label="Skip",
                        custom_id="Skip",
                        style=ButtonStyle.grey,
                        emoji="➡️")
    RewindButton = Button(custom_id="rewind",
                                style=ButtonStyle.grey,
                                emoji="⬅️")
    RestartButton = Button(#label="Restart",
                            custom_id="restart",
                            style=ButtonStyle.grey,
                            emoji="🔄")
    LoopButton = Button(#label="Toggle looping",
                        custom_id="loop",
                        style=ButtonStyle.grey,
                        emoji="🔂")

    ConfigButton = Button(  custom_id="configure",
                            style=ButtonStyle.grey,
                            emoji="⚙️" )


    FavouriteButton = Button(#label="Favourite",
                              custom_id="fav",
                              style=ButtonStyle.danger,
                              emoji="🤍")
    SubtitlesButton = Button(#label="Lyrics",
                            custom_id="subtitles",
                            style=ButtonStyle.primary,
                            emoji="✏️")  
    PlayAgainButton = Button(label="Replay this song !",
                              custom_id="play_again",
                              style=ButtonStyle.primary,
                              emoji="🎧")

    _audio_controller_btns = [RewindButton,SkipButton, PlayPauseButton,LoopButton,ConfigButton]

    @classmethod
    def AudioControllerButtons(self,song_queue,*,force_paused = False): #Force paused is forcing the emoji to pause, thats it
        
        v = View() 
        btns = self._audio_controller_btns.copy()

        btns[2].emoji = "▶️" if voice_state.is_paused(song_queue.guild) and not force_paused else "⏸"

        for item in btns:
            v.add_item(item)
        return v

    @classmethod
    def AfterAudioButtons(self):
        v = View() 
        for item in [self.PlayAgainButton]:
            v.add_item(item)
        return v

    #Buttons functionality 
    @staticmethod
    async def inform_changes(btn : Interaction,msg:str):
        if len(voice_state.get_non_bot_vc_members(btn.guild)) > 1:
            await btn.message.reply(content=f"{msg} by {btn.user.mention}",
                                    delete_after=30)

    @classmethod
    async def on_playpause_btn_press(self,btn : Interaction):
    
        if voice_state.is_paused(btn.guild):
            voice_state.resume_audio(btn.guild)
        else:
            voice_state.pause_audio(btn.guild)


        await btn.response.edit_message(view=self.AudioControllerButtons(btn.guild.song_queue))
        await self.inform_changes(btn,MessageString.paused_audio_msg)
    
    @classmethod
    async def on_rewind_btn_press(self,btn : Interaction):
        queue = btn.guild.song_queue
        if queue.history:
            voice_state.rewind_track(btn.guild)
            await btn.response.defer()
            await self.inform_changes(btn,MessageString.rewind_audio_msg)
        else:
            await btn.response.send_message(content="This is already the last track",ephemeral=True)

    @classmethod
    async def on_skip_btn_press(self,btn : Interaction):
        voice_state.skip_track(btn.guild)
        await btn.response.defer()
        await self.inform_changes(btn,MessageString.stopped_audio_msg)

    @classmethod
    async def on_loop_btn_press(self,btn : Interaction):
        await btn.response.defer()
        current_loop =btn.guild.song_queue.looping
        btn.guild.song_queue.looping = not current_loop
        await self.inform_changes(btn,MessageString.loop_audio_msg.format(convert.bool_to_str(btn.guild.song_queue.looping)))

    @classmethod
    async def on_config_btn_press(self,btn:Interaction):
        
        class ConfigModal(Modal,title = "Configuration of the audio"):
            volume_space = TextInput(label='Volume', style=discord.TextStyle.short,placeholder="1-200%",max_length=3,required=False)
            speed_space = TextInput(label='Speed', style=discord.TextStyle.short,placeholder="0.5-2.5",max_length=4,required=False)
            pitch_space = TextInput(label='Pitch', style=discord.TextStyle.short,placeholder="0.5-2.5",max_length=4,required=False)
            
            async def on_submit(_self, interaction: Interaction) -> None:

                guild = interaction.guild

                vol_changed,speed_changed,pitch_changed = False,False,False

                volume_to_set = str(_self.volume_space)
                new_speed = str(_self.speed_space)
                new_pitch = str(_self.pitch_space)

                if volume_to_set:

                    try: volume_percentage = convert.extract_int_from_str(volume_to_set)
                    except ValueError: ...
                    else:
                        from main import BotInfo
                        VOLUME_PERCENTAGE_LIMIT = BotInfo.VolumePercentageLimit
                        #Volume higher than the limit
                        if volume_percentage > VOLUME_PERCENTAGE_LIMIT and interaction.user.id != self.bot.owner_id:
                            return await interaction.response.send_message(f"🚫 Please enter a volume below {VOLUME_PERCENTAGE_LIMIT}% (to protect yours and other's ears 👍🏻)",ephemeral=True)
                        else:
                            vol_changed = not vol_changed
                            voice_client:discord.VoiceClient = guild.voice_client
                            true_volume :float               = volume_percentage / 100 * BotInfo.InitialVolume #Actual volume to be set to
                            
                            #Updating to the new value
                            guild.song_queue.volume = true_volume
                            if voice_client and voice_client.source:
                                voice_client.source.volume = true_volume


                if new_speed:

                    try:
                        new_speed = float(new_speed)
                        if new_speed <= 0:
                            voice_state.pause_audio(guild)
                            return await interaction.reply(MessageString.paused_audio_msg)
                        elif new_speed < 0.5 or new_speed > 5:
                            return await interaction.response.send_message("Speed can only range between `0.5-5`.",ephemeral=True)

                    except ValueError:
                        return await interaction.response.send_message("Invalid speed.",ephemeral=True)
                    else:
                        guild.song_queue.speed = new_speed
                        speed_changed = not speed_changed

                if new_pitch:
                    queue = guild.song_queue
                    
                    try:
                        if float(new_pitch) <= 0:
                            raise ValueError
                        #speed / pitch >= 0.5
                    except ValueError:
                        return  await interaction.response.send_message("Invalid pitch.",ephemeral=True)
                    else:
                        queue.pitch = float(new_pitch)
                        pitch_changed = not pitch_changed


                #Applying 
                await interaction.response.defer()
                
                if not (vol_changed or speed_changed or pitch_changed):
                    return

                await voice_state.update_audio_msg(guild)
                if pitch_changed or speed_changed:
                    if guild.voice_client and guild.voice_client._player and guild.song_queue:
                        voice_state.pause_audio(guild)
                        await voice_state.restart_track(guild)

                await self.inform_changes(btn,"New configuration of the audio set")

        await btn.response.send_modal(ConfigModal())

    @staticmethod
    async def on_play_again_btn_press(btn,bot):
        ctx = await bot.get_context(btn.message)

        URL = btn.message.embeds[0].url

        #Play the music
        await ctx.invoke(bot.get_command('play'),
                        query=URL,
                        btn=btn)

class UtilityButtons(View):
    @discord.ui.button(emoji="♻️",custom_id="delete",style=ButtonStyle.grey)
    async def delete_button(self,interaction : Interaction,btn):
        pass