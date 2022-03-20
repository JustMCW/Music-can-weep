from discord_emojis import Emojis

class Convert:
  #Decoration function

  def str_to_bool(string:str)->bool:
    #XOR logicgate 
    string = string.lower()
    _true = any([w in string for w in ["ye","ya","tr","on","op"]])
    _false = any([w in string for w in ["no","na","fa","of","cl"]])
    
    if _true and _false: return None
    elif _true or _false: return _true or not _false
    return None

  
  @staticmethod
  def bool_to_str(value:bool) -> str:
    if value == True: return f"On {Emojis.discord_on}"
    if value == False: return f"Off {Emojis.discord_off}"
    return "Unknown"
      
  @staticmethod
  def length_format(totalSeconds:int) -> str:
    if totalSeconds < 3600:
        Min = totalSeconds // 60
        Sec = totalSeconds % 60
        return f"{Min}:{Sec:02d}"
    else:
        Hours = totalSeconds // 3600
        Min = (totalSeconds % 3600) // 60
        Sec = totalSeconds % 60
        return f"{Hours}:{Min:02d}:{Sec:02d}"
      