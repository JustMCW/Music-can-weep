import os,json

FavouritesDir = "Database/Favourites/"
Indentation = 3

"""
Structure :

Database/Favourites/UserID.json 
    |
    V
{
  "Songname_1":"YoutubeURL_1",
  "Songname_2":"YoutubeURL_2",
}
"""

class Favourties:
  
  @staticmethod
  def get_data(user):
    if os.path.exists(FavouritesDir+str(user.id)+".json"):
      with open(FavouritesDir+str(user.id)+".json","r") as jsonf:
        return json.load(jsonf)
    raise FileNotFoundError

  @staticmethod
  def edit_data(user,edit):
    if not os.path.exists(FavouritesDir+str(user.id)+".json"):
      with open(FavouritesDir+str(user.id)+".json","w") as f:
        f.write("{}")
    
    with open(FavouritesDir+str(user.id)+".json","r+") as jsonf:
      old_data = json.load(jsonf)
      
      new_data = edit(old_data.copy())

    
      if len(new_data) < len(old_data):
        with open(FavouritesDir+str(user.id)+".json","w") as jsonfw:
          json.dump(new_data,jsonfw,indent = Indentation)
      elif len(new_data) != len(old_data):
        jsonf.seek(0)
        json.dump(new_data,jsonf,indent = Indentation)
      
    return new_data

  @classmethod
  def add_track(self,user, title:str, url:str):
    
    def new(data:dict)->dict:
      data[title] = url
      return data
      
    self.edit_data(user,new)

  @classmethod
  def remove_track(self,user,index: int):

    #If it is the last song in the track, remove the json file
    FavouritesList = self.get_data(user)
    if len(FavouritesList) <= 1:
      os.remove(FavouritesDir+str(user.id)+".json")
    else:
      def delete(data:dict)->dict:
        key = self.get_track_by_index(user,index)[0]
        del data[key]
        return data
      
      self.edit_data(user,delete)
    
  
  @classmethod
  def get_track_by_index(self,user, index:int)->(str,str):
      FavList = self.get_data(user)
        
      if index <= 0 or index > len(FavList):
        raise IndexError
      key = list(FavList)[index]
      return (key, FavList[key])
  