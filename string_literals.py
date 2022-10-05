#Replies / Message
from discord import PartialEmoji
class MyEmojis:
    YOUTUBE_ICON = "<:youtube_icon:937854541666324581>"
    discord_on = "<:discord_on:938107227762475058>"
    discord_off = "<:discord_off:938107694785654894>"
    cute_panda = "<:panda_with_headphone:938476351550259304>"

    pause = PartialEmoji.from_str("pause:1026270773066874920")
    resume = PartialEmoji.from_str("resume:1026270955426824242")
    rewind = PartialEmoji.from_str("rewind:1026270774182555698")
    fastforward = PartialEmoji.from_str("fastforward:1026270777647038465")

    loop = PartialEmoji.from_str("loop:1026270771875696691")
    singleloop = PartialEmoji.from_str("singleloop:1026270776334237697")

    previous = PartialEmoji.from_str("previous:1026276265705082955")
    skip = PartialEmoji.from_str("skip:1026276267550572564")

    config = PartialEmoji.from_str("config:1026270775294034100")
    queue = PartialEmoji.from_str("queue:1026277428735262732")

    download = PartialEmoji.from_str("download:1027010625030865047")

class MessageString:
    not_in_server_msg = "🏘 This command can only be used in servers ⚜️"
    not_playing_msg = "🔇 No audio playing right now 🎹"

    join_msg = "🎧 Successfully connected to {} 📡"
    leave_msg = "🔇 Successfully disconnected from {} 👋"
    user_not_in_vc_msg = "🎻 You must be in a voice channel first 🔊"
    bot_not_in_vc_msg = "📻 I am currently not in any voice channel 🔊"

    paused_audio_msg = "⏸ *Paused*"
    resumed_audio_msg = "▶️ *Resumed*"
    rewind_audio_msg = "⏪ *Rewinded*"
    skipped_audio_msg = "⏩ *Skipped*"

    stopped_audio_msg = "⏹ *Stopped playing*"
    restarted_audio_msg = "� *Restarted the song*"

    already_paused_msg = "⏸ Audio is already paused ☑️"
    already_resumed_msg = "🎤 Audio is already playing ~"
    same_vc_msg = "👍🏻 Already joined {}"
    free_to_use_msg = "🎧 Nothing is playing right now... meaning you are free to use it ! 👍�"

    loop_audio_msg = "🔂 Single-track looping has been set to {}"
    queue_loop_audio_msg = "🔁 Queue-looping has been set to {}"
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
