import re
# I stored some useful function here :)
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
    
def length_format(totalSeconds:int) -> str:
    if totalSeconds is None:
        return "Unknown"
    if totalSeconds < 3600:
        Min = int(totalSeconds // 60)
        Sec = int(totalSeconds % 60)
        return f"{Min}:{Sec:02d}"
    else:
        Hours = int(totalSeconds // 3600)
        Min = int((totalSeconds % 3600) // 60)
        Sec = int(totalSeconds % 60)
        return f"{Hours}:{Min:02d}:{Sec:02d}"
    
def timestr_to_sec(string:str)->int:
    #Its just a number.
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

def timestr_to_sec_ms(time_string:str) -> int:
    """timestr to sec but includes ms in the time stringi"""
    try:
        #Hour min and millisec are optional
        time_group:list = re.match(
            #           hour       min      sec     millisec
            pattern=r"(\d{1,2}:)?(\d{1,2}:)?(\d{1,2})(\.\d{3})?",
            string=time_string
        ).groups(None)
    except AttributeError:
        #No groups means no match found
        return None

    #Turn them into int and give each of them a variable
    hour,min,sec,millisec = map(lambda x: int(x.replace(":","").replace(".","")) if x is not None else x, time_group) 

    #if min doesnt exist but the hour does, then the hour must actually be the min (11:00 -> this is 11mins, not hours)
    if hour and min is None:
        min = hour
        hour = 0
    
    hour = hour or 0
    min = min or 0
    millisec = millisec or 0

    #Give back the result
    return (hour * 3600) + (min*60) + (sec) + (millisec / 1000)
