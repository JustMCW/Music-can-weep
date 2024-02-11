
import json
import discord

from typing import *
from keys import USERPLAYLIST_DATABASE

from music import SongTrack

Indentation = 4



class TrackJson(TypedDict):
    """Track as json"""
    title : str
    thumbnail : str
    url : str

class UserDatabase(Dict[str,List[TrackJson]]):
    """The place where a user's playlist and tracks are stored"""
    pass


# edit can return this to indicate the deletion of the entire user dir
DEL = "Del"
FAVOURITE = "<Favourite>"

"""
DESPERATE
Data structure :

In json file : 
database/playlistdb.json
    |
    V
userid : {
  "favourites" : {
    [
        {
            title : ez
            uploader : ez
            length : 1
            join_date : 10204040303
            url : ez
        }
    ]
  },
  "playlist1": {
    ...
  },
  "playlist2": {
    ...
  }
}

ORDER DOESN'T MATTER ?
"""

_User = discord.User | discord.Member

def encode_usr_id(id : int):
    first_digit = int(str(id)[0])
    return hex(id * first_digit)


def get_all_data() -> Dict[str,UserDatabase]:
    with open(USERPLAYLIST_DATABASE) as jsonf:
        return json.load(jsonf)


def get_data_for(user: _User) -> UserDatabase:
    return get_all_data().get(encode_usr_id(user.id),UserDatabase())

def get_all_playlist(user: _User, exclude_favourite = False) -> UserDatabase:
    playlists = get_data_for(user)
    if playlists and exclude_favourite:
        del playlists[FAVOURITE]
    return playlists

def edit_data(
    user : _User, 
    edit : Callable[[dict],dict]
) -> UserDatabase:
    """Edit a user's data with a function taken in as paramater
    returns the data after the edit."""
    data = get_all_data()
    encoded_id = encode_usr_id(user.id)

    edited_data = edit(
        data.get(encoded_id,{})
    )

    if not isinstance(edited_data,dict):
        raise TypeError(f"Expect dict from edit function, got `{type(edited_data)}`")

    if edited_data == DEL:
        del data[encoded_id]
    else:
        data[encoded_id] = edited_data

    with open(USERPLAYLIST_DATABASE,"w") as jsondb:
        json.dump(data,jsondb,indent = 4)

    return data[encoded_id]

    with open(USERPLAYLIST_DATABASE+str(user.id)+".json", "r+") as jsonf:
        old_data = json.load(jsonf)

        new_data = edit(old_data.copy())

        if len(new_data) < len(old_data):
            with open(USERPLAYLIST_DATABASE+str(user.id)+".json", "w") as jsonfw:
                json.dump(new_data, jsonfw, indent=Indentation)
        elif len(new_data) != len(old_data):
            jsonf.seek(0)
            json.dump(new_data, jsonf, indent=Indentation)

    return new_data


def get_playlist(
    user : discord.User,
    pl_name : str = FAVOURITE
):
    return get_data_for(user)[pl_name]


def make_playlist(
    user    : _User,
    pl_name : str
):
    """Make a new playlist for a user, 
    raises `ValueError` if playlist already exist"""
    def make_pl(data) -> dict:
        if data.get(pl_name):
            raise ValueError(f"Playlist : {pl_name} already exist for {user.name}.")
        data[pl_name] = {}
        return data

    edit_data(user, make_pl)

def delete_playlists(
    user : _User,
    pl_names : List[str]
):
    def del_pl(data) -> dict:
        for name in pl_names:
            del data[name]
        return data

    edit_data(user, del_pl)

def add_track(
    user : _User, 
    tracks : SongTrack|List[SongTrack],
    playlists : str|List[str] = FAVOURITE
) -> UserDatabase:
    """Add a track to the user's playlist database, returns the new playlist """
    if isinstance(playlists, str):
        playlists = [playlists]

    def append(data: dict) -> dict:

        def _apeend(playlistname):
            if not data.get(playlistname):
                data[playlistname] = []

            if isinstance(tracks,list):
                data[playlistname].extend([track.to_dict() for track in tracks])
            else:
                data[playlistname].append(tracks)

        if isinstance(playlists,list):
            for playlistname in playlists:
                _apeend(playlistname)
        else:
            _apeend(playlists)

        return data

    return edit_data(user, append)

def remove_tracks(
    user : _User, 
    index: List[int],
    playlist_name : str = FAVOURITE
) -> UserDatabase:

    # If it is the last song in the track, just remove the json file
    
    def delete(data: dict) -> dict:
        key,url = get_track_by_index(user, index)
        
        if data.get(playlist_name):
            raise KeyError(f"{playlist_name} is not a valid playlist for {user.name}")

        del data[playlist_name][key]

        if not data:
            return DEL
        return data

    return edit_data(user, delete)

def get_track_by_index(
    user: _User, 
    index: int
) -> tuple:
    FavList = get_data_for(user)

    if index < 0 or index >= len(FavList):
        raise IndexError(f"Invalid index : {index}")
        
    key = list(FavList)[index]
    return (key, FavList[key])
