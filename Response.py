#Replies / Message
class Emojis:
    YOUTUBE_ICON = "<:youtube_icon:937854541666324581>"
    discord_on = "<:discord_on:938107227762475058>"
    discord_off = "<:discord_off:938107694785654894>"
    cute_panda = "<:panda_with_headphone:938476351550259304>"


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

    bot_lack_perm_msg = f"I am missing the permission to do that :("

# MessageString.fav_empty_msg

import Convert
import discord
import discord_components

class Embeds:


    #The embed that display the audio's infomation + status
    
    def generate_search_result_attachments(search_result) -> dict:
        """
        Returns the embed + buttons for a youtube search result returned by the `search_from_youtube` function
        """
        #Add the buttons and texts for user to pick
        choices_string:str  = ""
        components    :list = []

        for i,video in enumerate(search_result):
            title = video["title"]["runs"][0]["text"]
            length = video["lengthText"]["simpleText"]

            choices_string += f'{i+1}: {title} `[{length}]`\n'
            components.append(discord_components.Button(label=str(i+1),custom_id=str(i),style=discord_components.ButtonStyle.blue))
        
        return {
            "embed":discord.Embed(title="🎵  Select a song you would like to play : ( click the buttons below )",
                                  description=choices_string,
                                  color=discord.Color.from_rgb(255, 255, 255)),
            "components": discord_components.ActionRow(components)
        }


    @staticmethod
    def audio_playing_embed(queue,foundLyrics:bool) -> discord.Embed:
        """the discord embed for displaying the audio that is playing"""
        from Music import voice_state
        
        SongTrackPlaying = queue[0]

        YT_creator = getattr(SongTrackPlaying,"channel",None) 
        Creator = YT_creator or getattr(SongTrackPlaying,"uploader")
        Creator_url = getattr(SongTrackPlaying,"channel_url",getattr(SongTrackPlaying,"uploader_url",None))
        Creator = "[{}]({})".format(Creator,Creator_url) if Creator_url else Creator

        return discord.Embed(title= SongTrackPlaying.title,
                            url= SongTrackPlaying.webpage_url,
                            color=discord.Color.from_rgb(255, 255, 255))\
                \
                .set_author(name=f"Requested by {SongTrackPlaying.requester.display_name}",
                            icon_url=SongTrackPlaying.requester.avatar_url)\
                .set_image(url = SongTrackPlaying.thumbnail)\
                \
                .add_field(name=f"{Emojis.YOUTUBE_ICON} YT channel" if YT_creator else "💡 Creator",
                           value=Creator)\
                .add_field(name="↔️ Length",
                            value=f'`{Convert.length_format(getattr(SongTrackPlaying,"duration"))}`')\
                .add_field(name="📝 Lyrics",
                            value=f'*{"Available" if foundLyrics else "Unavailable"}*')\
                \
                .add_field(name="🔊 Voice Channel",
                            value=f"{queue.guild.voice_client.channel.mention}")\
                .add_field(name="📶 Volume ",
                            value=f"`{voice_state.get_volume_percentage(queue.guild)}%`")\
                .add_field(name="🔂 Looping",
                            value=f'**{Convert.bool_to_str(queue.looping)}**')

    NoTrackSelectedEmbed = discord.Embed(title=f"{Emojis.cute_panda} No track was selected !",
                                        description=f"You thought for too long ( {2} minutes ), use the command again !",
                                        color=discord.Color.from_rgb(255, 255, 255))