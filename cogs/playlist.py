import datetime
import asyncio
import discord

from typing import *

from discord import app_commands,Interaction
from discord.ui import select, View,button
from discord.ext import commands
from music import voice_utils,create_track_from_url
from literals import ReplyStrings

import convert

import custom_errors
# import database.user_playlist as favourite
from music import get_song_queue
from database import user_playlist

class PlaylistSelector(View):

    def __init__(
        self, 
        *, 
        playlists: user_playlist.UserDatabase, 
        callback: Callable[[Interaction, Dict],Coroutine[Any,Any,None]],
        call_once: bool = True,
        components : List[discord.ui.Item] = [],
        timeout: Optional[float] = 180,

        **kwargs
    ):
        @select(
            custom_id="playlist_selecter",
            options=[
                discord.SelectOption(label=name, value=name) 
                for name in playlists
            ],
            
            **kwargs
        )
        async def on_select(self: View, interaction: Interaction, _select: discord.ui.Select):
            values = interaction.data["values"] #type: ignore
            
            selected_playlist : Dict[str,List[user_playlist.TrackJson]] = {}
            for name in playlists:
                if name in values:
                    selected_playlist[name] = playlists[name]

            await callback(interaction, selected_playlist) 
            if call_once:
                return self.stop()

        
        self.__view_children_items__= (*components, on_select)
        super().__init__(timeout=timeout)

class TrackSelector(View):
    def __init__(
        self, 
        *, 
        playlist: List[user_playlist.TrackJson],
        callback: Callable[[Interaction, Dict[int,user_playlist.TrackJson]],Coroutine[Any,Any,None]],
        timeout: Optional[float] = 180
    ):
            
        @select(
            custom_id="track_selector",
            options=[
                discord.SelectOption(
                    label=f"{index}. {track['title']}",
                    value=str(index)
                ) 
                for index, track in enumerate(playlist)
            ],
            max_values=len(playlist)
        )
        async def on_select(self, interaction: Interaction, _select):
            selected_indexs = interaction.data["values"] #type: ignore
            selected_indexs = list( map( lambda i: int(i), selected_indexs) )

            selected_tracks = {}

            for index, track in enumerate(playlist):
                if index in selected_indexs:
                    selected_tracks[index] = track

            await callback(interaction, selected_tracks)

            self.stop()

        self.__view_children_items__=[on_select]
        super().__init__(timeout=timeout)

class PlaylistAndTrackSelector(View):
    """Runs the playlist selector then the track selector, 
    the final callback would recieve : 
        - an interaction
        - the tracks of the playlist 
        - the name of the playlist 
    """
    def __init__(
        self,
        *,
        playlists : user_playlist.UserDatabase,
        inner_selector_message : str,
        callback : Callable[[Interaction, str, Dict[int,user_playlist.TrackJson]],Coroutine[Any,Any,None]],
        timeout: Optional[float] = 180
    ):
        async def inner_callback(interaction: Interaction, playlist: dict):
            playlist_name = list(playlist.keys())[0]

            # so we can also pass the playlist_name paramater to the last callback
            async def transformed_callback (interaction: Interaction, tracks: Dict[int,user_playlist.TrackJson]):
                await callback(interaction,playlist_name,tracks)

            await interaction.response.send_message(
                content=inner_selector_message,
                view=TrackSelector(
                    playlist=playlists[playlist_name],
                    callback=transformed_callback
                ),
                ephemeral=True,
            )

        PlaylistSelector(
            playlists=playlists,
            callback=inner_callback,
        )
        super().__init__(timeout=timeout)


class PlaylistCommands(commands.Cog):

    def __init__(self,bot : commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @commands.guild_only()
    @commands.hybrid_command(
        aliases=["save", "fav"],
        description='👍🏻 Add the current song playing to your favourites',
        usage="{}fav"
    )
    async def favourite(self, ctx:commands.Context):

        #No audio playing
        if not voice_utils.is_playing(ctx.guild):
            return await ctx.reply(ReplyStrings.free_to_use_msg)

        Track = music.get_song_queue(ctx.guild)[0]

        #Add to the list
        position:int = user_playlist.add_track(ctx.author, Track.title, Track.webpage_url)

        #Responding
        await ctx.reply(ReplyStrings.added_fav_msg.format(Track.title,position))

#Unfavouriting song

    @commands.hybrid_command(
        aliases=['unfav'],
        description='❣🗒 Remove a song from your favourites',
        usage="{}unfav 3"
    )
    async def unfavourite(self, ctx:commands.Context,*,index):
        
        try:
            index = convert.extract_int_from_str(index) - 1
            removedTrackTitle = user_playlist.get_track_by_index(ctx.author,index)[0]
            user_playlist.remove_track(ctx.author,index)
        except ValueError:
            await ctx.reply("✏ Please enter a vaild index")
        except FileNotFoundError:
            await ctx.reply(ReplyStrings.fav_empty_msg)
        else: 
            await ctx.reply(f"`{removedTrackTitle}` has been removed from your favourites")
        
#Display Favourites

    @commands.hybrid_command(
        aliases=["favlist", "myfav"],
        description='❣🗒 Display every song in your favourites',
        usage="{}myfav"
    )
    async def display_favourites(self, ctx:commands.Context):

        #Grouping the list in string
        try:
            favs_list = user_playlist.get_playlist(ctx.author)
        except FileNotFoundError:
            return await ctx.reply(ReplyStrings.fav_empty_msg)

        wholeList = ""
        for index, track_data in enumerate(favs_list):
            wholeList += "***{}.*** {}\n".format(index + 1,track_data["title"])

        #embed =>
        favouritesEmbed = discord.Embed(
            title=f"🤍 🎧 Favourites of {ctx.author.name} 🎵",
            description=wholeList,
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=datetime.datetime.now()
        ).set_footer(
            text="Your favourites would be the available in every server"
        )

        #sending the embed
        await ctx.reply(embed=favouritesEmbed)

    @commands.hybrid_group(
        aliases=["pl"],
        description="the commands for managing your personal playlist",
    )
    async def playlist(self, ctx: commands.Context):
        pass

    @playlist.command(
        aliases=[],
        description="display tracks in your playlist",
    )
    async def display(self, ctx: commands.Context):

        playlists = user_playlist.get_all_playlist(ctx.author)
        playlist_name = list(playlists.keys())[0]

        def display_embed(name : str):
            return discord.Embed(
                title=f"Your tracks in ***{name}***",
                description="\n".join(
                    (
                        f"`[{index+1}]` [{track['title']}]({track['url']})" 
                        for index,track in enumerate(playlists[name])
                    )
                )
            )

        async def display_callback(interaction: Interaction, selected_playlist: dict):
            playlist_name = list(selected_playlist.keys())[0]
            await interaction.response.edit_message(embed=display_embed(playlist_name))

        @button(custom_id="add_playlist",emoji="➕")
        async def add(_, interaction: Interaction, btn):
            await ctx.invoke(self.create)
            # interaction
            # try:
            #     user_playlist.make_playlist(ctx.author,name)
            # except ValueError:
            #     await ctx.reply("Playlist already exitst, please pick another name", ephemeral = True)
            # else:
            #     await ctx.reply(f"Playlist `{name}` has been created successfully", ephemeral = True)


        @button(custom_id="remove_playlist",emoji="➖")
        async def delete(_, interaction, btn):
            await ctx.invoke(self.delete)

        @button(custom_id="remove_track",emoji="🗑️")
        async def remove_track(_, interaction, btn):
            await ctx.invoke(self.remove_tracks)

        selector = PlaylistSelector(
            playlists=playlists,
            callback=display_callback,
            call_once=False,
            components=[add,delete,remove_track]
        )

        await ctx.reply(
            "~",
            embed=display_embed(playlist_name),
            view=selector,
        )
  
    @playlist.command(
        aliases=["new"],
        description="Make a new playlist",
    )
    @app_commands.describe(name="The name for the new playlist")
    async def create(self, ctx: commands.Context, name: str):
        user = ctx.author
        try:
            user_playlist.make_playlist(user,name)
        except ValueError:
            await ctx.reply("Playlist already exitst, please pick another name", ephemeral = True)
        else:
            await ctx.reply(f"Playlist `{name}` has been created successfully", ephemeral = True)

    @playlist.command(
        description="save the current queue as your playlist",
    )
    async def save(self, ctx: commands.Context, name: str):
        user = ctx.author
        try:
            user_playlist.make_playlist(user,name)
            
        except ValueError:
            await ctx.reply("Playlist already exitst, please pick another name", ephemeral = True)
        else:
            user_playlist.add_track(ctx.author,list(get_song_queue(ctx.guild)),[name])
            await ctx.reply(f"Saved the queue as  playlist`{name}`", ephemeral = True)

    @playlist.command(
        aliases=[],
        description="Make a new playlist",
    )
    async def delete(self, ctx: commands.Context):

        playlists = user_playlist.get_all_playlist(ctx.author)
        
        if not playlists:
            await ctx.reply("You have no exisiting playlists, run \"/playlist create\" to make one !", ephemeral=True)

        # Find which playlist to delete
        async def select_playlist(interaction : Interaction, playlists: Dict[str,list]):
            user_playlist.delete_playlists(ctx.author, list(playlists.keys()))
            await interaction.response.send_message(
                f"Successfully deleted {len(playlists)} playlist(s)",
                ephemeral=True
            )

        await ctx.send(
            view=PlaylistSelector(
                playlists=playlists,
                callback=select_playlist,
                max_values=len(playlists),
                timeout=60,
            )
        )

    @playlist.command(
        aliases=["append"],
        description="Add the track playing to one of your playlist",
    )
    async def add_track(self, ctx: commands.Context):
        
        queue = get_song_queue(ctx.guild)
        try:
            track = queue[0]
        except KeyError:
            raise custom_errors.NoAudioPlaying

        playlists = user_playlist.get_all_playlist(ctx.author)
        
        if not playlists:
            await ctx.reply("You have no exisiting playlists, run \"/playlist create\" to make one !", ephemeral=True)

        # Find which playlist to add
        async def select_playlist(interaction : Interaction, playlists: Dict[str,list]):
            
            user_playlist.add_track(
                ctx.author,
                [track],
                list(playlists.keys())
            )

            await interaction.response.send_message(
                f"Successfully added **{track.title}** to {len(playlists)} playlist(s)",
                ephemeral=True
            )

        await ctx.send(
            content=f"Select playlist(s) to add *{track.title}*",
            view=PlaylistSelector(
                playlists=playlists,
                callback=select_playlist,
                timeout=60,
                max_values=len(playlists),
            ),
            ephemeral=True,
        )
     
    @playlist.command(
        aliases=[],
        description="Remove tracks from selected playlist",
    )
    async def remove_tracks(self, ctx: commands.Context):
        
        playlists = user_playlist.get_all_playlist(ctx.author)
        if not playlists:
            await ctx.reply("You have no exisiting playlists, run \"/playlist create\" to make one !", ephemeral=True)

        async def select_track_from_playlist(
            interaction: Interaction, 
            playlist_name: str,
            tracks: Dict[int,user_playlist.TrackJson]
        ): 
            # FIXME : make it use edit data instead
            indexs = list(tracks.keys())
            user_playlist.remove_tracks(
                ctx.author,
                indexs, # the index of the tracks
                playlist_name,
            )

            await interaction.response.send_message(f"Successfully removed `{len(indexs)}` tracks from playlist {playlist_name}")

        await ctx.send(
            content="Select a playlist :",
            view=PlaylistAndTrackSelector(
                playlists=playlists,
                inner_selector_message="Select tracks to remove :",
                callback=select_track_from_playlist,
                timeout=60,
            )
        )
     
    # The boss command
    @commands.guild_only()
    @playlist.command(
        description='🎧 Add all tracks in your play list to the queue',
    )
    async def play(self, ctx:commands.Context):
        
        async def selected_playlist_callback(interaction: discord.Interaction, playlists: dict):
            name = list(playlists.keys())[0]
            playlist = playlists[name]
            queue = get_song_queue(ctx.guild)

            await interaction.response.defer()
            mes = await start_message.edit(
                content=f"{ctx.author.name} requests to plays their playlist : {name} ( {len(playlist)} tracks)",
                view=None
            )

            def play_after():
                queue.clear()
                for i,trackjson in enumerate(playlist):
                    queue.append(create_track_from_url(trackjson["url"], requester=ctx.author))
                    if i == 0:
                        queue.play_first()

            if ctx.voice_client is None:
                await ctx.author.voice.channel.connect()
                play_after()
                await music.create_audio_message(queue, mes)
            else:
                ctx.voice_client.stop()
                queue._call_after = play_after

        start_message = await ctx.reply(
            view=PlaylistSelector(
                playlists=user_playlist.get_all_playlist(ctx.author),
                callback=selected_playlist_callback,
                max_values=1,
            ),
            ephemeral=False,
        )

async def setup(bot : commands.Bot):
    await bot.add_cog(PlaylistCommands(bot))
