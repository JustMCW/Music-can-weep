
import json
import discord

from typing import Callable,Dict
from keys import USERPLAYLIST_DATABASE

from music.song_track import SongTrack

Indentation = 4


class UserDatabase(Dict[str,dict]):
    """The place where a user's playlist and tracks are stored"""
    pass

# edit can return this to indicate the deletion of the entire user dir
DEL = "Del"
FAV_KEY = "__favourite__"

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

def encode_usr_id(id : int):
    first_digit = int(str(id)[0])
    return hex(id * first_digit)


def get_all_data() -> Dict[int,UserDatabase]:
    with open(USERPLAYLIST_DATABASE) as jsonf:
        return json.load(jsonf)

def get_data_for(user: discord.User) -> UserDatabase:
    return get_all_data().get(encode_usr_id(user.id),{})

def edit_data(
    user : discord.User, 
    edit : Callable[[dict],dict]
) -> UserDatabase:
    """Edit a user's data with a function taken in as paramater
    returns the data after the edit."""
    data = get_all_data()
    encoded_id = encode_usr_id(user.id)

    output = edit(
        data.get(encoded_id,{})
    )

    if output == DEL:
        del data[encoded_id]
    else:
        data[encoded_id] = output

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

def make_playlist(
    user : discord.User,
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

def delete_playlist(
    user : discord.User,
    pl_name : str
):
    def del_pl(data) -> dict:
        del data[pl_name]
        return data

    edit_data(user, del_pl)


def add_track(
    user : discord.User, 
    track : SongTrack,
    playlist_name : str = FAV_KEY
) -> UserDatabase:
    """Add a track to the user's playlist database, returns the new playlist """

    def append(data: dict) -> dict:
        if not data.get(playlist_name):
            # make_playlist(user,playlist_name)
            data[playlist_name] = []

        data[playlist_name].append(track.to_dict())
        return data

    return edit_data(user, append)

def remove_track(
    user : discord.User, 
    index: int,
    playlist_name : str = FAV_KEY
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

def get_track_by_index(user, index: int) -> tuple:
    FavList = get_data_for(user)

    if index < 0 or index >= len(FavList):
        raise IndexError(f"Invalid index : {index}")
        
    key = list(FavList)[index]
    return (key, FavList[key])