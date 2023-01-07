# Literal Replies & Emojis

import discord
import math
import convert
from typing import TYPE_CHECKING

from discord import PartialEmoji, VoiceChannel

if TYPE_CHECKING:
    from music.song_queue import SongQueue
from music.song_track import YoutubeTrack,WebFileTrack,WebsiteSongTrack
from music.voice_constants import PROGRESSBAR_SIZE

class MyEmojis:
    youtube_icon = "<:youtube_icon:937854541666324581>"
    discord_on = "<:discord_on:938107227762475058>"
    discord_off = "<:discord_off:938107694785654894>"
    cute_panda = "<:panda_with_headphone:938476351550259304>"

    PAUSE = "⏸"  # or PartialEmoji.from_str("pause:1026270773066874920")
    RESUME = "▶️"  # or PartialEmoji.from_str("resume:1026270955426824242")

    REWIND = "⏪"  # or PartialEmoji.from_str("rewind:1026270774182555698")
    # or PartialEmoji.from_str("fastforward:1026270777647038465")
    FASTFORWARD = "⏩"
    FAVOURITE = "🤍"

    PREVIOUS = "⬅️"  # or PartialEmoji.from_str("previous:1026276265705082955")
    SKIP = "➡️"  # or PartialEmoji.from_str("skip:1026276267550572564")

    # or PartialEmoji.from_str("singleloop:1026270776334237697")
    TRACKLOOP = "🔂"
    QUEUELOOP = "🔁"  # or PartialEmoji.from_str("loop:1026270771875696691")

    QUEUE = PartialEmoji.from_str("queue:1026277428735262732")

    CONFIG = PartialEmoji.from_str("config:1026270775294034100")
    DOWNLOAD = PartialEmoji.from_str("download:1027010625030865047")


class ReplyStrings:
    not_in_server_msg = "🏘 This command can only be used in servers ⚜️"
    not_playing_msg = "🔇 No audio playing right now 🎹"

    @staticmethod
    def JOIN(voice_channel: VoiceChannel) -> str:
        return f"🎧 Successfully connected to {voice_channel.mention} 📡"
    @staticmethod
    def LEAVE(voice_channel: VoiceChannel) -> str:
        return f"🔇 Successfully disconnected from {voice_channel.mention} 👋"

    user_not_in_vc_msg = "🎻 You must be in a voice channel first 🔊"
    bot_not_in_vc_msg = "📻 I am currently not in any voice channel 🔊"

    PAUSE = "⏸ *Paused*"
    RESUME = "▶️ *Resumed*"
    REWIND = "⏪ *Rewinded*"
    SKIP = "⏩ *Skipped*"

    STOP = "⏹ *Stopped playing*"
    RESTART = "🔄 *Restarted the track*"

    @classmethod
    def TRACK_LOOP(cls, value: bool) -> str:
        return f"🔂 Track-looping has been set to {cls.prettify_bool(value).lower()}"

    @classmethod
    def QUEUE_LOOP(cls, value: bool) -> str:
        return f"🔁 Queue-looping has been set to {cls.prettify_bool(value).lower()}"

    already_paused_msg = "⏸ Audio is already paused ☑️"
    already_resumed_msg = "🎤 Audio is already playing ~"
    same_vc_msg = "👍🏻 Already joined {}"
    free_to_use_msg = "🎧 Nothing is playing right now... meaning you are free to use it ! 👍�"

    now_play_msg = "**🎧 Now playing 🎤**"

# Fav_msg
    added_fav_msg = "✅ `{}` has been added to your favourites at **#{}** !"
    removed_fav_msg = "👋 `{}` has been removed from your favourites"
    already_in_fav_msg = "✅ `{}` is already in your favourites"
    fav_empty_msg = "🗒 Your favourite list is currently empty"

# Errors_msg
    missing_perms_msg = "🚫 You are lacking the permissions to perform this command"
    missing_arg_msg = "💭 You are missing `{}` for this command to work"
    command_not_found_msg = "💭 This command was not found ( {} )"
    user_not_found_msg = f"🔍 User was not found 👻"
    channel_not_found_msg = f"🔍 Channel was not found 💬"

    invaild_bool_msg = "🪗 Enter a vaild value : `on / off`"
    queue_empty_msg = "📦 Queue is empty ... play some songs !"
    queue_disabled_msg = "This server has queuing disabled, run \"{}config queue on\" to turn it on again (requires admin permission)"

    bot_lack_perm_msg = "I am missing the permission : `[{}]` to do that :("

    @staticmethod
    def prettify_bool(value: bool) -> str:
        return f"On {MyEmojis.discord_on}" if value else f"Off {MyEmojis.discord_off}"


class ReplyEmbeds:

    @staticmethod
    def audio_displayer(queue : 'SongQueue') -> discord.Embed:
        """returns  discord embed for displaying the audio that is playing"""
        current_track = queue.current_track

        if not current_track:
            return

        #Init embed + requester header + thumbnail
        rembed = discord.Embed( title= current_track.title,
                                url= current_track.webpage_url or current_track.source_url,
                                color=discord.Color.from_rgb(255, 255, 255) ) \
                .set_author(name=f"Requested by {current_track.requester.display_name}" ,
                            icon_url=current_track.requester.display_avatar ) \
                .set_image( url=current_track.thumbnail )

        # Creator field
        if isinstance(current_track,WebsiteSongTrack):

            if isinstance(current_track,YoutubeTrack):
                #Author field
                channel,channel_url = current_track.channel
                rembed.add_field(
                    name=f"{MyEmojis.youtube_icon} YT channel",
                    value=f"[{channel}]({channel_url})"
                )

            else:
                uploader, uploader_url = current_track.uploader
                rembed.add_field(
                    name=f"💡 Creator",
                    value=f"[{uploader}]({uploader_url})"
                )

        # File size field
        if isinstance(current_track, WebFileTrack):
            rembed.add_field(
                name=f"File format",
                value=f"{current_track.file_format}"
            ).add_field(
                name=f"File size",
                value=f"{current_track.file_size}"
            )
                    
            
        emoji_before = "━" or '🟥' 
        emoji_mid = "●"
        emoji_after = "━" or '⬜️'
        #Durartion field + Progress bar
        if current_track.duration:
            try:
                progress = max(
                    math.floor(
                        (queue.time_position / current_track.duration) * PROGRESSBAR_SIZE
                    ),
                    1
                )
            except AttributeError:
                progress = 1

            progress_bar = (emoji_before * (progress-1)) + emoji_mid + emoji_after * (PROGRESSBAR_SIZE-progress)
            duration_formmated = convert.length_format(current_track.duration)
            rembed.add_field(name="↔️ Length",
                                value=f'`{duration_formmated}`')
            rembed.set_footer(text=f"{convert.length_format(queue.time_position)} [ {progress_bar} ] {duration_formmated}")

            rembed.add_field(name="📝 Lyrics",
                                value=f"*Available in {len(current_track.subtitles)} languages*" if getattr(current_track,"subtitles",None) else "*Unavailable*")


        # General stuff
        rembed.add_field(name="📶 Volume ",
                            value=f"`{queue.volume_percentage}%`")
        rembed.add_field(
            name="⏩ Tempo",
            value=f"`{queue.tempo:.2f}`"
        ).add_field(
            name="ℹ️ Pitch",
            value=f'`{queue.pitch:.2f}`'
        )

        rembed.add_field(
            name="🔊 Voice Channel",
            value=f"{queue.guild.voice_client.channel.mention}"
        ).add_field(
            name="🔂 Looping",
            value=f'**{ReplyStrings.prettify_bool(queue.looping)}**' 
        ).add_field(
            name="🔁 Queue looping",
            value=f'**{ReplyStrings.prettify_bool(queue.queue_looping)}**'
        )
                
        if queue.get(1):
            rembed.add_field(
                name="🎶 Upcoming track",
                value=queue[1].title
            )
        elif queue.auto_play and not queue.queue_looping:
            rembed.add_field(
                name="🎶 Upcoming track (Auto play)",
                value= current_track.recommend.title
            )

        return rembed