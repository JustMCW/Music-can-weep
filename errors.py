#I mean ... just look at their name lol Ovo


from discord.ext.commands import errors

class custom_errors:
  
  class NotInVoiceChannel(errors.CommandError): pass

  class NoAudioPlaying(errors.CommandError): pass
  
  class UserNotInVoiceChannel(errors.CommandError): pass

  class QueueEmpty(errors.CommandError): pass

  class QueueDisabled(errors.CommandError): pass