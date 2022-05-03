import asyncio
import discord
from click import BadParameter

from discord_components import Select, SelectOption, Button, ButtonStyle,Interaction
from Response import MessageString
from subtitles import Subtitles
import Favourites
import Convert
from Music import voice_state

#BUTTONS
class Buttons:
    
    #Button Templates
    PauseButton = Button(label="Pause",
                          custom_id="pause",
                          style=ButtonStyle.blue,
                          emoji="⏸")
    ResumeButton = Button(label="Resume",
                          custom_id="resume",
                          style=ButtonStyle.green,
                          emoji="▶️")
    SkipButton = Button(label="Skip",
                        custom_id="Skip",
                        style=ButtonStyle.blue,
                        emoji="⏩")
    RestartButton = Button(label="Restart",
                            custom_id="restart",
                            style=ButtonStyle.grey,
                            emoji="🔄")

    FavouriteButton = Button(label="Favourite",
                              custom_id="fav",
                              style=ButtonStyle.red,
                              emoji="🤍")
    LoopButton = Button(label="Toggle looping",
                        custom_id="loop",
                        style=ButtonStyle.grey,
                        emoji="🔂")
    SubtitlesButton = Button(label="Lyrics",
                            custom_id="subtitles",
                            style=ButtonStyle.blue,
                            emoji="✏️")  
    PlayAgainButton = Button(label="Play this song again !",
                              custom_id="play_again",
                              style=ButtonStyle.blue,
                              emoji="🎧")

    AudioControllerButtons=[[PauseButton,ResumeButton,SkipButton,RestartButton],
                            [FavouriteButton,LoopButton,SubtitlesButton]].copy()

    AfterAudioButtons=[[PlayAgainButton,FavouriteButton]].copy()

    #Buttons functionality 
    @staticmethod
    async def inform_changes(btn,msg:str):
        if len(voice_state.get_non_bot_vc_members(btn.guild)) > 1:
            await btn.message.reply(content=f"{msg} by {btn.author.mention}",
                                    delete_after=30)

    def subpress_failed_message(func):
        async def wrapper(*args,**kwargs):
            
            btn:Interaction = None
            for arg in args + tuple(kwargs.values()):
                if isinstance(arg,Interaction): 
                    btn = arg
                    break

            if btn is None:
                raise BadParameter(f"There must be a button object as a argument in {func.__name__}. It was not found from : {list(func.__code__.co_varnames)}")
            
            try:
                await btn.edit_origin(content=btn.message.content)
            except discord.HTTPException:
                ...
            finally:
                return await func(*args,**kwargs)

        return wrapper

    @classmethod
    async def on_pause_btn_press(self,btn):
        if voice_state.is_paused(btn.guild):
            await btn.respond(type=4, content=MessageString.already_paused_msg)
        else:
            await btn.edit_origin(content=btn.message.content)
            voice_state.pause_audio(btn.guild)
            await self.inform_changes(btn,MessageString.paused_audio_msg)

    @classmethod
    async def on_resume_btn_press(self,btn):
        if not voice_state.is_paused(btn.guild):
            await btn.respond(type=4, content=MessageString.already_resumed_msg)
        else:
            await btn.edit_origin(content=btn.message.content)
            voice_state.resume_audio(btn.guild)
            await self.inform_changes(btn,MessageString.resumed_audio_msg)
    @classmethod
    @subpress_failed_message
    async def on_skip_btn_press(self,btn):
        voice_state.skip_audio(btn.guild)
        await self.inform_changes(btn,MessageString.stopped_audio_msg)

    @classmethod
    @subpress_failed_message
    async def on_restart_btn_press(self,btn):
        await voice_state.restart_audio(btn.guild)
        await self.inform_changes(btn,MessageString.restarted_audio_msg)

    @classmethod
    async def on_loop_btn_press(self,btn):
        await btn.edit_origin(content=btn.message.content)
        current_loop =btn.guild.song_queue.looping
        btn.guild.song_queue.looping = not current_loop
        await self.inform_changes(btn,MessageString.loop_audio_msg.format(Convert.bool_to_str(btn.guild.song_queue.looping)))

    @staticmethod
    async def on_favourite_btn_press(btn):
        await btn.respond(type=5)
        title = btn.message.embeds[0].title
        url = btn.message.embeds[0].url
        await btn.respond(content=MessageString.added_fav_msg.format(title,Favourites.add_track(btn.author, title, url)))

    @staticmethod
    async def on_subtitles_btn_press(btn,bot):
        await btn.respond(type=5)
        CurrentTrack = btn.guild.song_queue[0]

        languages =getattr(CurrentTrack,"subtitles",None)
        if languages is None: 
            return

        from langcodes import Language

        options = []
        for lan in languages.keys():
                languageName = Language.get(lan)
                if languageName.is_valid(): 
                    options.append(SelectOption(label=languageName.display_name(), value=lan))
                    if len(options) == 24: 
                        break

        title = CurrentTrack.title

        
        await btn.respond(
            type=4,
            content = f"🔠 Select subtitles language for ***{title}***",
            components=[
            Select(placeholder="select language", options=options)
            ]
        )
        try:
            option = await bot.wait_for(
            event='select_option',
            check=lambda opt: opt.author == btn.author,
            timeout=60)
        except asyncio.TimeoutError:
            pass
        else:
            selected_language = option.values[0]
            modernLanguageName = Language.get(
            selected_language).display_name()

            UserDM = await option.author.create_dm()
            await UserDM.send(
            content=f"**{title} [ {modernLanguageName} ] **")
            url,subtitle_text = Subtitles.extract_subtitles(languages,selected_language)
            await Subtitles.send_subtitles(
                UserDM,
                '\n'.join(subtitle_text)
            )
            await UserDM.send(content=f"( The subtitle looks glitched ? View the source text file here : {url})")

    @staticmethod
    async def on_play_again_btn_press(btn,bot):
        ctx = await bot.get_context(btn.message)

        URL = btn.message.embeds[0].url

        if voice_state.get_current_vc(ctx.guild):...

        #Play the music
        await ctx.invoke(bot.get_command('play'),
                        query=URL,
                        btn=btn)