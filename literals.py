""" Literal Replies & Emojis """

from string import Template
from discord import PartialEmoji

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


    JOIN = "🎧 Successfully connected to {0.mention} 📡"
    LEAVE = "🔇 Successfully disconnected from {0.mention} 👋"

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
    missing_arg_msg = Template("💭 You are missing `$param` for this command to work")
    command_not_found_msg = "💭 This command was not found ( {} )"
    user_not_found_msg = f"🔍 User was not found 👻"
    channel_not_found_msg = f"🔍 Channel was not found 💬"

    invaild_bool_msg = "🪗 Enter a vaild boolean : `on / off`"

    invalid_paramater = Template("🪗 Bad value : `$param`")
    queue_empty_msg = "📦 Queue is empty ... play some songs !"
    queue_disabled_msg = "This server has queuing disabled, run \"{}config queue on\" to turn it on again (requires admin permission)"

    bot_lack_perm_msg = "I am missing the permission : `[{}]` to do that :("

    @staticmethod
    def prettify_bool(value: bool) -> str:
        return f"On {MyEmojis.discord_on}" if value else f"Off {MyEmojis.discord_off}"
