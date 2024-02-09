import asyncio
import discord

from discord.ui  import View,Select
from discord.ext import commands
from my_buttons  import UtilityButtons

import music
from music   import voice_utils
from convert import timestr_to_sec_ms,length_format

TIMEOUT_SECONDS  = 60 * 2

class LyrcisCommand(commands.Cog):
    def __init__(self, bot : commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @commands.guild_only()
    @commands.hybrid_group()
    async def lyrics(self, ctx: commands.Context):
        pass

    @commands.guild_only()
    @lyrics.command(
        description="Sends the entire subtitle text"
    )
    async def send(self,ctx: commands.Context):
        guild = ctx.guild
        queue = music.get_song_queue(guild)
        current_track = queue[0]

        if not isinstance(current_track, music.WebsiteSongTrack):
            return

        try:
            subtitle_dict = current_track.subtitles
            if not subtitle_dict:
                raise ValueError
        except (AttributeError,ValueError):
            return await ctx.reply("Sorry, The song playing now don't have subtitle supported ! (At least not in the youtube caption)") #Current song has no subtitle

        from langcodes import Language
        
        if len(subtitle_dict.keys()) > 1:
            options = []
            for lan in subtitle_dict.keys():
                languageName = Language.get(lan)
                if languageName.is_valid(): 
                    options.append(discord.SelectOption(label=languageName.display_name(), value=lan))
                    if len(options) == 24: 
                        break

            title = current_track.title

            select_language_view = View().add_item(Select(placeholder="Select your language for subtitle", options=options))
            del_msg = await ctx.send(
                content = f"🔠 Select a language for the lyrics of ***{title}***",
                view=select_language_view
            )

            try:
                interaction : discord.Interaction = await self.bot.wait_for(
                    'interaction',
                    check=lambda interaction: interaction.data["component_type"] == 3 and interaction.user.id == ctx.author.id,
                    timeout=TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                return
            await del_msg.delete()
            selected_language = interaction.data["values"][0]
        else: #There is only one language avaiable
            selected_language = list(subtitle_dict.keys())[0]

        modern_lang_name = Language.get(selected_language).display_name()
        from subtitles import Subtitles
        url,subtitle_text = Subtitles.extract_subtitles(subtitle_dict,selected_language)
        try:
            await ctx.send(
                embed=discord.Embed(title=f"{current_track.title} [{modern_lang_name}]",description=subtitle_text),
                view=UtilityButtons()
            )
        except discord.HTTPException as httpe:
            await ctx.send(f"Unable to send subtitle, [{httpe.code}], sourcelink : {url}")

    @commands.guild_only()
    @lyrics.command(
        description="Sends bits of the subtitle text as the player goes on"
    )
    async def stream(self,ctx: commands.Context):

        ### Get the language for the lyrics
        from langcodes import Language

        guild = ctx.guild
        queue = music.get_song_queue(guild)
        current_track = queue[0]
        try:
            subtitle_dict = current_track.subtitles
            if not subtitle_dict:
                raise ValueError
        except (AttributeError,ValueError):
            return await ctx.reply("Sorry, The song playing now don't have subtitle supported ! (At least not in the youtube caption)") #Current song has no subtitle

        
        if len(subtitle_dict.keys()) > 1:
            #Make the language a select_option object
            options = []
            for lan in subtitle_dict.keys():
                languageName = Language.get(lan)
                if languageName.is_valid(): 
                    options.append(discord.SelectOption(label=languageName.display_name(), value=lan))
                    if len(options) == 24: 
                        break

            select_language_view = View().add_item(Select(placeholder="Select your language for subtitle", options=options))
            del_msg = await ctx.send(
                content = f"🔠 Select a language for the lyrics of ***{current_track.title}***",
                view=select_language_view
            )

            #Make the interaction
            try:
                interaction : discord.Interaction = await self.bot.wait_for(
                    'interaction',
                    check=lambda interaction: interaction.data["component_type"] == 3 and interaction.user.id == ctx.author.id,
                    timeout=TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                return
            finally:
                await del_msg.delete()

            selected_language = interaction.data["values"][0]
        else: 
            #There is only one language avaiable, don't even bother asking.
            selected_language = list(subtitle_dict.keys())[0]

        m = await ctx.send(embed=discord.Embed(title="Loading...")) #The message used for displaying lyrics

        # Getting the subtitle text, using request.
        import requests
        import re
        subtitle_url = current_track.subtitles[selected_language][5]["url"]
        subtitle_content = requests.get(subtitle_url).content.decode("utf-8")
        subr = re.findall(r"^(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})\n((^.+\n)+)\n",subtitle_content,re.MULTILINE)
        
        subr = list(map( #Format the time in floating points
            lambda sub:(
                timestr_to_sec_ms(sub[0]),
                timestr_to_sec_ms(sub[1]),
                sub[2]
            )
            ,subr
        )) 

        # Streaming the lyrics into discord

        prev_text = ""
        offset = 0.3 # the higher the earilier


        #the stream, a while loop.
        while queue.source and queue.get(0) == current_track and queue.time_position:
            for i,(timing,end_timing,_) in enumerate(subr):

                if timing > queue.time_position + offset and i:
                    text = subr[i-1][2]
                    
                    #Text changed
                    if prev_text != text:
                        prev_text = text
                        await m.edit(embed=discord.Embed(
                            title="Streaming the lyrics",
                            description=text
                        ).set_footer(
                            text=f"{length_format(timing)} - {length_format(end_timing)}"
                        ))

                    break
            
            await asyncio.sleep(0.1)


        await m.edit(embed=discord.Embed(
                        title="The stream ended.",
                        description="..."
                    ),view=UtilityButtons())
        

async def setup(bot : commands.Bot):
    await bot.add_cog(LyrcisCommand(bot))