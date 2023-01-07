import discord
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from music.song_queue import SongQueue

#Add 2 property to the guild
class GuildExt(discord.Guild):
    """Extended version of the original guild class,

    with `song_queue` and `database` added to its attributes"""
    @property
    def song_queue(self) -> 'SongQueue':
        """Represents the song queue of the guild"""
        from music.song_queue import SongQueue
        return SongQueue.get_song_queue_for(self)

    @property
    def database(self) -> dict:
        """Represents the database which is from `Database.DiscordServers.json` of the guild"""
        import database.server as serverdb
        return serverdb.read_database_of(self)

discord.Guild.song_queue = GuildExt.song_queue
discord.Guild.database = GuildExt.database
discord.GuildExt = GuildExt