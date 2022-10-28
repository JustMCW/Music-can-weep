#I mean ... just look at their name lol Ovo

from discord.ext.commands import errors

class NotInVoiceChannel(errors.CommandError): pass
errors.NotInVoiceChannel = NotInVoiceChannel

class NoAudioPlaying(errors.CommandError): pass
errors.NoAudioPlaying = NoAudioPlaying

class UserNotInVoiceChannel(errors.CommandError): pass
errors.UserNotInVoiceChannel = UserNotInVoiceChannel

class QueueEmpty(errors.CommandError): pass
errors.QueueEmpty = QueueEmpty

class QueueDisabled(errors.CommandError): pass
errors.QueueDisabled = QueueDisabled

class AudioNotSeekable(errors.CommandError): pass
errors.AudioNotSeekable = AudioNotSeekable

