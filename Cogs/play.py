#Built-ins
import asyncio
import logging

from typing    import List,Optional

#Third party libaries
import yt_dlp as youtube_dl

import discord
from discord.ext   import commands
from discord       import app_commands
from discord.ui    import View,Button


import convert
import custom_errors

import music
from music import TrackDomain

from youtube_utils import YoutubeVideo,url_matcher,search_from_youtube
from webhook_logger import *

from typechecking import *
from literals import MyEmojis

from youtube_utils import extract_yt_url_from
#----------------------------------------------------------------#
TIMEOUT_SECONDS  = 60 * 2
logger = logging.getLogger(__name__)

from enum import Enum,auto

class TrackPosition(Enum):
    Last = auto()
    Next = auto()
    Now  = auto()
    Random = auto()

DOMAIN_TO_EMOJI = {
    TrackDomain.YOUTUBE : MyEmojis.youtube_icon,
    TrackDomain.SOUNDCLOUD : "☁️",
    TrackDomain.DISCORD_ATTACHMENT : "🔵",
}

# Random functions that i don't know where to place :

to_member = lambda member: ensure_type(member, discord.Member)

#Take the search result from the function above and make them into buttons and embed
def generate_search_result_attachments(search_result : List[YoutubeVideo]) -> dict:
    """
    Returns the embed + buttons for a youtube search result returned by the `search_from_youtube` function
    """
    #Add the buttons and texts for user to pick
    choices_string:str  = ""


    class _components(View):...
    components = _components()

    for i,video in enumerate(search_result):
        
        title = video.title
        length = video.length

        choices_string += f'{i+1}: {title} `[{length}]`\n'
        components.add_item(Button(label=f"{i+1}",custom_id=f"{i}",style=discord.ButtonStyle.blurple,row=0))
    
    return {
        "embed":discord.Embed(title="🎵  Select a song you would like to play : ( click the buttons below )",
                                description=choices_string,
                                color=discord.Color.from_rgb(255, 255, 255)),
        "view": components
    }

async def play_track_handler(
    ctx: commands.Context, 
    url: str, 
    reply_msg: discord.Message,
    position = TrackPosition.Last, 
    author: Optional[Union[discord.Member,discord.User]] = None 
):

    if not author:
        author = ctx.author
        if not author:
            return

    guild = ensure_exist(ctx.guild)
    queue = music.get_song_queue(guild)

    # Extract & create the song track
    try:
        NewTrack = music.create_track_from_url(
            url=url,
            requester=author,
        )

    # Extraction Failed
    except youtube_dl.utils.YoutubeDLError as occured_error:
        logger.warning(occured_error.__class__.__name__)

        utils = youtube_dl.utils
        

        for error,error_message in {
            utils.UnsupportedError      : "Sorry, this url is not supported !",
            utils.UnavailableVideoError : "Video was unavailable",
            utils.DownloadError         : str(occured_error).replace("ERROR: ",""),
        }.items():
            if isinstance(occured_error,error):
                return await reply_msg.reply(f"An error occurred : {error_message}")

        # Raise the error if it wasn't in the above dictionary
        # since I'm not too sure what else could cause the error
        logger.error(occured_error)
        raise occured_error

    # Extraction was Successful

    voice_client = ensure_type_optional(guild.voice_client, discord.VoiceClient)
    
    # Stop current audio if queuing is disabled
    if voice_client is not None: 
        if not queue.enabled:
            voice_client.stop()
            # Idk, wait for the track to be popped ?
            while queue.current_track:
                await asyncio.sleep(0.5)

    # Joining the voice channel
    else: 
        #User left during the loading was taking place
        user_vc = author.voice
        if not user_vc:
            return await reply_msg.edit(content = "User left the voice channel, the track was cancled.")
        voice_client = await music.join_voice_channel(ensure_exist(user_vc.channel))
        voice_client = ensure_exist(voice_client)
        
    
    result_position = 1
    
    # No matter what the option is, if the queue is empty, it is going to be at the first place
    if position == TrackPosition.Last or not queue:
        queue.append(NewTrack)
        result_position = len(queue)-1

    elif position == TrackPosition.Next:
        result_position = 1
        queue.insert(result_position,NewTrack)

    elif position == TrackPosition.Random:
        from random import randint
        result_position = randint(1,max(1,len(queue)-1))
        queue.insert(result_position,NewTrack)

    elif position == TrackPosition.Now:
        
        if voice_client.source:
            
            def insert():
                queue.appendleft(NewTrack)
                queue.play_first()

            NewTrack.request_message = reply_msg
            queue._call_after = insert
            voice_client.stop()

        else:
            queue.appendleft(NewTrack)
            queue.play_first()

        return await queue.create_audio_message(reply_msg or ctx.channel)

    # There is a track playing already
    if queue.get(1) and queue.enabled and position != TrackPosition.Now:

        await reply_msg.edit(
            embed=discord.Embed(
                title = NewTrack.title,
                url=NewTrack.webpage_url,
                description="Has been added to the queue.",
                color=discord.Color.from_rgb(255, 255, 255),
            ).add_field(
                name="Length ↔️",
                value=f"`{convert.length_format(NewTrack.duration)}`",
            ).add_field(
                name = "Position in queue 🔢",
                value=result_position,
            ).set_thumbnail(
                url = NewTrack.thumbnail,
            )
        )

        # Since there is a field in the audio message indcating the next track to be played
        await queue.update_audio_message() 
        
        # we still want to play the first track
        NewTrack.request_message = reply_msg#await ctx.fetch_message(reply_msg.id)

        if voice_client.source:
            return

        await queue.create_audio_message(ctx.channel)
        NewTrack = queue[0]
    else:
    # #Make our audio message
        await queue.create_audio_message(reply_msg or ctx.channel)

    # Let ffmpeg initialize itself
    # await asyncio.sleep(1.5)
    
    # Playing the first track in queue 
    try:
        queue.play_first()
    
    # Happens when 2 user try to play tracks at the same time, or something else idk
    except discord.errors.ClientException as cl_exce:
            if cl_exce.args[0] == 'Already playing audio.':
                if queue.enabled:
                    return await reply_msg.edit(embed=discord.Embed(title = f"\"{NewTrack.title}\" has been added to the queue",
                                            color=discord.Color.from_rgb(255, 255, 255))
                                .add_field(name="Length ↔️",
                                            value=f"`{convert.length_format(NewTrack.duration)}`")
                                .add_field(name = "Position in queue 🔢",
                                            value=len(queue)-1)
                            .set_thumbnail(url = NewTrack.thumbnail))
                    
                return await ctx.reply("Unable to play this track because another tracks was requested at the same time")
            raise cl_exce


#COMMANDS
class PlayCommands(commands.Cog):
    def __init__(self,bot):
        self.bot:commands.Bot = bot

        super().__init__()


    @commands.guild_only()
    @commands.hybrid_command(
        aliases=["p","music"],
        description='🔎 Search and play audio with a given YOUTUBE link or from keywords 🎧',
        usage="{0}play https://www.youtube.com/watch?v=GrAchTdepsU\n{0}p mood\n{0}play fav 4"
    )
    @app_commands.describe(query="URL or search keyword on youtube.")
    @app_commands.describe(position="where the track will be placed")
    async def play(
        self,
        ctx:commands.Context,
        *,
        query: str, #URL / Favourite track index / Keyword
        position: TrackPosition = TrackPosition.Last
    ):
        guild = ensure_exist(ctx.guild)
        author : discord.Member = to_member(ctx.author) if not isinstance(ctx,discord.Interaction) else to_member(ctx.user)

        voice_client = ensure_type_optional(guild.voice_client,discord.VoiceClient) or author.voice #It can be either the bot's vc or the user's vc
        reply_msg = None  #This will be the message for the audio message

        # Check for voice channel
        if voice_client is None:
            raise custom_errors.UserNotInVoiceChannel("You need to be in a voice channel.")

        destination_url = query
        url_match = url_matcher(query)
        # From keyword
        if not url_match:
            # Search it up
            
            try:
                search_result = search_from_youtube(query,ResultLengthLimit=5)
            except IndexError:
                return await ctx.reply(f"No search result was found for `{query}` ...")

            choice_message = await ctx.reply(**generate_search_result_attachments(search_result))
            
            # Get which video the user wish to play

            try:
                choice_interaction: discord.Interaction = await ctx.bot.wait_for(
                    "interaction",
                    timeout = TIMEOUT_SECONDS,
                    # Make sure that it is the user we want who presses the button
                    check   = lambda interaction: 
                        interaction.data.get("component_type") == 2 and
                        "custom_id" in interaction.data.keys()  and
                        interaction.message.id == choice_message.id
                )
            
            # Timeouted
            except asyncio.TimeoutError:
                return await choice_message.edit(
                    view = None, # Remove the buttons
                    embed = discord.Embed(
                        title       = f"{MyEmojis.cute_panda} No track was selected !",
                        description = f"You thought for too long ( {int(TIMEOUT_SECONDS/60)} minutes ), use the command again !",
                        color       = discord.Color.from_rgb(255, 255, 255)
                    )
                )

            # Received option
            selected_index = int(choice_interaction.data["custom_id"]) #type: ignore

            await choice_interaction.response.edit_message(content=f"{MyEmojis.youtube_icon} Song **#{selected_index+1}** in the youtube search result has been selected",view = None)
            reply_msg = await ctx.fetch_message(choice_message.id)
            destination_url = f'https://www.youtube.com/watch?v={search_result[selected_index].videoId}'
            logger.info(f"Selected {destination_url}")
        # From url 
        else:
            message = ""

            # idk prop have some weird ass error that happens when the url has extra info in the back
            if url_match["domain"] in TrackDomain.YOUTUBE.value:
                
                destination_url = extract_yt_url_from(destination_url)
                
            for domain in list(TrackDomain):
                if url_match["domain"] in domain.value:
                    message = f"{DOMAIN_TO_EMOJI.get(domain,'🎵')} A {domain.value[0].capitalize()} URL is selected"

            if not message:
                return await ctx.send("Oops ! Only Youtube and Soundcloud links are supported ! ")
            reply_msg = await ctx.reply(message)
            destination_url = destination_url.replace("<","").replace(">","")
            
        # We now have the exact url that lead us to the audio regardless of what the user've typed, 
        # Let's extract the audio and play it.
        
        await play_track_handler(
            ctx,
            destination_url,
            reply_msg,
            position,
            author
        )

    @commands.guild_only()
    @commands.hybrid_command(
        aliases=["pf"],
        description='🎧 Upload a file and play it',
    )
    @app_commands.describe(file="your file to be played")
    @app_commands.describe(position="where the track will be placed")
    async def playfile(
        self,
        ctx:commands.Context,
        *,
        file: discord.Attachment, #URL / Favourite track index / Keyword
        position: TrackPosition = TrackPosition.Last
    ):
        # Check for voice channel
        voice_client = ctx.voice_client or to_member(ctx.author).voice #It can be either the bot's vc or the user's vc
        if voice_client is None:
            raise custom_errors.UserNotInVoiceChannel("You need to be in a voice channel.")

        reply_msg = await ctx.reply("File track")
        destination_url = file.url
        await play_track_handler(
            ctx,
            destination_url,
            reply_msg,
            position
        )



    watch_list = {}
    @commands.guild_only()
    @commands.hybrid_command(
        description="Listen on the message you send & add it to the queue. Until the command `stop_listen` is called"
    )
    @app_commands.describe(url_only="Only detects your message if it contains a url. Otherwise it will search")
    async def listen(
        self,
        ctx:commands.Context,
        url_only : bool = True,
        position : TrackPosition=TrackPosition.Last,
    ):
        author = ctx.author
        channel = ctx.channel

        key = (channel.id,author.id)

        self.watch_list[key] = 1

        await ctx.reply("Send some tracks and I will add them (/stop_listen to stop).")
        
        while self.watch_list.get(key):
            msg : discord.Message = await self.bot.wait_for("message")
            if msg.channel.id != channel.id or msg.author.id != author.id:
                continue

            content = msg.content
            
            if not url_only:
                await self.play(ctx,query=content,position=position)
            elif url_matcher(content):
                await play_track_handler(ctx,content,await msg.reply("Gotcha ..!"),position)


    @commands.guild_only()
    @commands.hybrid_command(
        description="Stops the bot from listening and add tracks triggered by the `listen` command"
    )
    async def stop_listen(
        self,
        ctx:commands.Context
    ):
        author = ctx.author
        channel = ctx.channel

        key = (channel.id,author.id)
        try:
            del self.watch_list[key]
        except KeyError:
            await ctx.reply("Nah I wasn't listening anyway.")
        else:
            await ctx.reply("Ok Ima stop listening to what you say")
      
async def setup(bot: commands.Bot):
    cog = PlayCommands(bot)
    await bot.add_cog(cog)
    
    @bot.tree.context_menu()
    async def play(interaction: discord.Interaction, message: discord.Message):
        if not interaction.guild:
            return await interaction.response.send_message("This is a dm, you have to be in a server to play stuff.",ephemeral=True)
        author = interaction.user

        

        if not interaction.guild.voice_client:
            if not author.voice:
                return await interaction.response.send_message("You gotta join a voice channel.",ephemeral=True)
        
        url = message.content

        if not url_matcher(message.content):
            if not message.embeds or not url_matcher(message.embeds[0].url):
                return await interaction.response.send_message("That message does not contain a url, or im just noob at finding links.",ephemeral=True)
            url = message.embeds[0].url

        await interaction.response.defer(ephemeral=True)
        msg = await message.reply("Playing this because why not")
        await play_track_handler(interaction,url,msg,author=interaction.user)

    @bot.tree.context_menu(name="Join their vc")
    async def join_user(interaction: discord.Interaction, member: discord.Member):
        voice = member.voice
        if not voice:
            return await interaction.response.send_message("That user is not in a voice channel.",ephemeral=True)
        await music.join_voice_channel(voice.channel)
        await interaction.response.send_message(f"{interaction.user.name} forced me to join the {member.name}'s voice channel.")