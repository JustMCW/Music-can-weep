#I mean ... just look at their name lol Ovo

from discord.ext import commands

class custom_errors:
  
  class NotInVoiceChannel(Exception): pass

  class NoAudioPlaying(Exception): pass
  
  class UserNotInVoiceChannel(Exception): pass

  class QueueEmpty(Exception): pass

  class QueueDisabled(Exception): pass