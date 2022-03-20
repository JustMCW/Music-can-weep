from Music.song_track import SongTrack
from main import BOT_INFO

class Queue:
  def __init__(self):
    self.volume = BOT_INFO.InitialVolume
     
    self.looping = BOT_INFO.InitialLooping
    self.queue_looping = BOT_INFO.InitialQueueLooping

    self._queue = []

  def __str__(self) -> str:
    return str(self._queue)
  
  def __getitem__(self,index:int) -> SongTrack:
    return self._queue[index]

  def __len__(self) -> int:
    return len(self._queue)
  
  def __iter__(self) -> iter:
    return iter(self._queue)

  def __iadd__(self,newTrack:SongTrack):
    self._queue.append(newTrack)
    return self

  def __isub__(self,pos:int):
    self._queue.pop(pos)
    return self
  
  def swap(self,pos1:int,pos2:int):
    
    if pos1 >=  len(self) or pos1 >=  len(self):
      raise IndexError
      
    first = self._queue.pop(pos1)
    second = self._queue.pop(pos2)

    self._queue.insert(pos1,second)
    self._queue.insert(pos2,first)
  
  def shuffle(self):
    from random import shuffle
    shuffle(self._queue)