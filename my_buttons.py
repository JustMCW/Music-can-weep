import asyncio
import discord
from discord import ButtonStyle,Interaction
from discord.ui import View,Button,Select,Modal,TextInput
from string_literals import MessageString
from subtitles import Subtitles

import favourites
import convert
from Music import voice_state

#BUTTONS
class Buttons:
    
    #Button Templates
    PlayPauseButton = Button(#label="Pause",
                          custom_id="playpause",
                          style=ButtonStyle.grey,
                          emoji="⏸") #Default playing
    SkipButton = Button(#label="Skip",
                        custom_id="Skip",
                        style=ButtonStyle.grey,
                        emoji="▶️")
    RestartButton = Button(#label="Restart",
                            custom_id="restart",
                            style=ButtonStyle.grey,
                            emoji="🔄")
    RewindButton = Button(custom_id="rewind",
                                style=ButtonStyle.grey,
                                emoji="◀️")
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

    _audio_controller_btns = [RewindButton, PlayPauseButton,SkipButton,LoopButton,
                               ConfigButton].copy()

    @classmethod
    def AudioControllerButtons(self):
        v = discord.ui.View() 
        for item in self._audio_controller_btns:
            v.add_item(item)
        return v

    @classmethod
    def AfterAudioButtons(self):
        v = discord.ui.View() 
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
        ac_btns = self._audio_controller_btns
    
        if voice_state.is_paused(btn.guild):
            voice_state.resume_audio(btn.guild)
            ac_btns[1].emoji = "⏸"
        else:
            voice_state.pause_audio(btn.guild)
            ac_btns[1].emoji = "▶️"

        v=View()
        for item in ac_btns: v.add_item(item)

        await btn.response.edit_message(view=v)
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
    async def on_restart_btn_press(self,btn : Interaction):
        await voice_state.restart_track(btn.guild)
        await btn.response.defer()
        await self.inform_changes(btn,MessageString.restarted_audio_msg)

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
            speed_space = TextInput(label='Speed', style=discord.TextStyle.short,placeholder="0.5-2.5",max_length=3,required=False)
            pitch_space = TextInput(label='Pitch', style=discord.TextStyle.short,placeholder="0.5-2.5",max_length=3,required=False)
            
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
                        from main import BOT_INFO
                        from Cogs.music import VOLUME_PERCENTAGE_LIMIT
                        #Volume higher than the limit
                        if volume_percentage > VOLUME_PERCENTAGE_LIMIT and interaction.user.id != self.bot.owner_id:
                            return await interaction.response.send_message(f"🚫 Please enter a volume below {VOLUME_PERCENTAGE_LIMIT}% (to protect yours and other's ears 👍🏻)",ephemeral=True)
                        else:
                            vol_changed = not vol_changed
                            voice_client:discord.VoiceClient = guild.voice_client
                            true_volume :float               = volume_percentage / 100 * BOT_INFO.InitialVolume #Actual volume to be set to
                            
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
    async def on_favourite_btn_press(btn : Interaction):
        return await btn.response.defer()
        title = btn.message.embeds[0].title
        url = btn.message.embeds[0].url
        await btn.response.send_message(content=MessageString.added_fav_msg.format(title,favourites.add_track(btn.user, title, url)))

    @staticmethod
    async def on_subtitles_btn_press(btn : Interaction, bot : discord.Client):
        await btn.response.defer(ephemeral=True,thinking=True)
        current_track = btn.guild.song_queue[0]
        try:
            subtitle_dict = current_track.subtitles
        except AttributeError:
            return #Current song has no subtitle

        from langcodes import Language

        from discord import SelectOption
        options = []
        for lan in subtitle_dict.keys():
            languageName = Language.get(lan)
            if languageName.is_valid(): 
                options.append(SelectOption(label=languageName.display_name(), value=lan))
                if len(options) == 24: 
                    break

        title = current_track.title

        select_language_view = View().add_item(Select(placeholder="select language", options=options))
        await btn.followup.send(
            content = f"🔠 Select subtitles language for ***{title}***",
            view=select_language_view
        )

        try:
            interaction : Interaction = await bot.wait_for(
                'interaction',
                check=lambda interaction: interaction.data["component_type"] == 3 and interaction.user.id == btn.user.id,
                timeout=60
            )
        except asyncio.TimeoutError:
            pass
        else:
            selected_language = interaction.data["values"][0]
            modernLanguageName = Language.get(selected_language).display_name()

            UserDM = await interaction.user.create_dm()
            await UserDM.send(
            content=f"**{title} [ {modernLanguageName} ] **")
            url,subtitle_text = Subtitles.extract_subtitles(subtitle_dict,selected_language)
            await Subtitles.send_subtitles(
                UserDM,
                '\n'.join(subtitle_text)
            )
            await UserDM.send(content=f"( The subtitle looks glitched ? View the source text file here : {url})")

    @staticmethod
    async def on_play_again_btn_press(btn,bot):
        ctx = await bot.get_context(btn.message)

        URL = btn.message.embeds[0].url

        if voice_state.get_current_vc(ctx.guild): ...

        #Play the music
        await ctx.invoke(bot.get_command('play'),
                        query=URL,
                        btn=btn)