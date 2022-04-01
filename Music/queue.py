from Music.song_track import SongTrack
from main import BOT_INFO

class Queue:
  def __init__(self):
    self.volume = BOT_INFO.InitialVolume
    self.audio_control_status = None

    self.looping = BOT_INFO.InitialLooping
    self.queue_looping = BOT_INFO.InitialQueueLooping

    self.bounded_channel = None
    self.audio_message = None

    self._queue = []

  def __str__(self) -> str:
    return str(self._queue)
  
  def __getitem__(self,index:int) -> SongTrack:
    try:
      return self._queue[index]
    except IndexError:
      return None

  def __len__(self) -> int:
    return len(self._queue)
  
  def __iter__(self) -> iter:
    return iter(self._queue)

  def __iadd__(self,newTrack:SongTrack):
    self._queue.append(newTrack)
    print(newTrack.title,"is added to the queue")
    return self

  def __isub__(self,pos:int):
    print(self._queue.pop(pos).title,"is removed from the queue")
    return self
  
  @property
  def total_length(self):
    ttlen = 0

    for track in self:
      ttlen += track.duration

    return ttlen

  def move_first_to_last(self):
    self += self._queue.pop(0)

  def swap(self,pos1:int,pos2:int):

    if pos1 >= len(self) or pos1 == 0:
      raise IndexError
    
    if pos2 >= len(self) or pos2 == 0:
      raise IndexError
    
    if pos1 == pos2:
      raise IndexError

    self._queue[pos1] , self._queue[pos2] = self._queue[pos2] , self._queue[pos1]
  
  def shuffle(self):
    from random import shuffle
    #Exclude the first item ( playing )
    queue_copy = self._queue[1:]

    shuffle(queue_copy)
    
    #add it back after shuffling
    queue_copy.insert(0,self._queue[0])

    self._queue = queue_copy