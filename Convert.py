from string_literals import Emojis
import re
#I stored some useful function here :)
def extract_int_from_str(string:str)->int:
    """
    Find the first number in a string, raises `ValueError` if not found
    """
    try:
        return int(re.findall(r'\d+', string)[0])
    except IndexError:
        raise ValueError("No number was found from the string")

def str_to_bool(string:str)->bool:
    #XOR logicgate 
    string = string.lower()
    _true = any([w in string for w in ["ye","ya","tr","on","op"]])
    _false = any([w in string for w in ["no","na","fa","of","cl"]])
    
    if _true and _false: 
        return None
    elif _true or _false: 
        return _true or not _false
    return None


def bool_to_str(value:bool) -> str:
    if value == True: return f"On {Emojis.discord_on}"
    if value == False: return f"Off {Emojis.discord_off}"
    return "Unknown"
    
def length_format(totalSeconds:int) -> str:
    if totalSeconds < 3600:
        Min = int(totalSeconds // 60)
        Sec = int(totalSeconds % 60)
        return f"{Min}:{Sec:02d}"
    else:
        Hours = int(totalSeconds // 3600)
        Min = int((totalSeconds % 3600) // 60)
        Sec = int(totalSeconds % 60)
        return f"{Hours}:{Min:02d}:{Sec:02d}"
    
def time_to_sec(string:str)->int:
    #Its just a number .
    try: return int(string) 
    except ValueError: pass

    try:
        #Hours
        #                       1 2      :        3    4         :         5    6
        pattern = re.compile(r"(\d+)\s*[:,\-h]\s*([0-5]?\d)\s*[:,\-m]\s*([0-5]?\d)")
        match = list(pattern.finditer(string))[0]

        return (int(match.group(1)) * 3600) + (int(match.group(2))*60) + int(match.group(3))
    except IndexError:
        try:
            # Mins
            #                       3 4      :        5    6
            pattern = re.compile(r"(\d+)\s*[:,\-m]\s*([0-5]?\d)")
            match = list(pattern.finditer(string))[0]
            return int(match.group(1)) * 60 + int(match.group(2))
        except IndexError:
            try: 
                #Literal seconds
                pattern = re.compile(r"(\d+)")
                match = list(pattern.finditer(string))
            
                if len(match) != 1:
                    raise IndexError
                    

                return int(match[0].group(1))
            except IndexError:
                return None
