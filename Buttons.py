import asyncio
import discord
from discord import ButtonStyle,Interaction
from discord.ui import View,Button,Select
from Response import MessageString
from subtitles import Subtitles

import Favourites
import Convert
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
                        emoji="⏭")
    RestartButton = Button(#label="Restart",
                            custom_id="restart",
                            style=ButtonStyle.grey,
                            emoji="🔄")
    RewindButton = Button(custom_id="rewind",
                                style=ButtonStyle.grey,
                                emoji="⏮")
    LoopButton = Button(#label="Toggle looping",
                        custom_id="loop",
                        style=ButtonStyle.grey,
                        emoji="🔂")

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

    _audio_controller_btns = [RewindButton, PlayPauseButton,SkipButton,RestartButton,LoopButton]

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
        ac_btns = self._audio_controller_btns.copy()
    
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
        await self.inform_changes(btn,MessageString.loop_audio_msg.format(Convert.bool_to_str(btn.guild.song_queue.looping)))

    @staticmethod
    async def on_favourite_btn_press(btn : Interaction):
        return await btn.response.defer()
        title = btn.message.embeds[0].title
        url = btn.message.embeds[0].url
        await btn.response.send_message(content=MessageString.added_fav_msg.format(title,Favourites.add_track(btn.user, title, url)))

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