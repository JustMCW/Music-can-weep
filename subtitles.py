import requests
import re
import asyncio
import logging
from googletrans import Translator

translator = Translator()

def sec_in_time_string(time_string:str) -> int:
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

    #if min doesnt exist but the hour then the hour must actually be the min
    if hour and min is None:
        min = hour
        hour = 0
    
    hour = hour or 0
    min = min or 0
    millisec = millisec or 0

    #Give back the result
    return (hour * 3600) + (min*60) + (sec) + (millisec / 1000)

#Thing that mess with subtitle
class Subtitles:

    @staticmethod
    def find_subtitle_and_language(sub_catergory:dict=None)->tuple:
        if sub_catergory:
            if len(sub_catergory) > 0:
                return True, sub_catergory
        return False, None

    @staticmethod
    def filter_subtitle(content:str)->str:
        while True:
            #<color1234> my Text </color1234>
            try:
                content = content.replace(
                    content[content.index('<'):content.index('>') + 1],
                    ''
                )
            except ValueError:
                return content

    @staticmethod
    def extract_subtitles(subtitles_list:list, language:str)->list:
        language_catergory = subtitles_list.get(language)
        
        if not language_catergory:
            language_catergory = list(subtitles_list.values())[0]
        subtitles_url = language_catergory[4]["url"]
        subtitles_file:str = requests.get(subtitles_url).content.decode("utf-8")
        subtitles = []
        is_complex = False
        for line in subtitles_file.splitlines():
            if line == "\n".encode('utf-8'): continue
            # line = line.decode('utf-8')
            if "##" in line:
                is_complex = True
                continue
            if line == ' ' or line == '': continue
            skipKeywords = [
                "-->", "Kind:", "WEBVTT", "Language", '::cue', '}', 'Style:'
            ]
            if any(x in str(line) for x in skipKeywords): 
                continue

            if is_complex:
                line = Subtitles.filter_subtitle(line)
                if len(subtitles) > 2:
                    if line == subtitles[-1] or line == subtitles[-2]:
                        continue
            subtitles.append(line)

        return subtitles_url,subtitles

    @staticmethod
    async def send_subtitles(channel, subtitles_text:str):
        full = ""
        for text in subtitles_text.splitlines():
            if len(full + text) > 1999:
                await channel.send(f"{full}")
                full = ""
            else:
                full += text+"\n"
        if len(full) > 1: 
            await channel.send(full)

    @staticmethod
    async def sync_subtitles(queue,channel,song_track):
        if not queue.sync_lyrics:
            return logging.info("Syncing disabled")
        sub_options:dict = getattr(song_track,"subtitles",None)
        if not sub_options:
            return 
        lang = sub_options.get("ja") or sub_options.get("zh-TW") or sub_options.get("zh-HK") or sub_options.get("zh-CN") or sub_options.get("en") or list(sub_options.values())[0]
        subtitle:str = requests.get(lang[4]["url"]).content.decode("utf-8")
        subtitle_dict = {}

        logging.info(lang[4]["url"])

        for indx,line in enumerate(subtitle.splitlines()):
            if "-->" in line:
                match = re.match(r"^(\d{2}:\d{2}:\d{2}\.\d{3}) --> (\d{2}:\d{2}:\d{2}\.\d{3})$",line)
                if not match: 
                    return logging.warning("Complex cannot be synced")
                subtitle_dict[(sec_in_time_string(match.group(1))-0.5,sec_in_time_string(match.group(2)))] = subtitle.splitlines()[indx+1]

        async def tt(text):
            if sub_options.get("ja"):
                pron = translator.translate(text,src="ja",dest="ja").pronunciation
                if pron != text:
                    return await channel.send(f"{text}\n{pron}",delete_after = 30)
            return await channel.send(f"{text}",delete_after = 30)

        async def loop():

            for indx,((start,end),text) in enumerate(subtitle_dict.items()):
                await asyncio.sleep((start if indx == 0 else start - list(subtitle_dict.keys())[indx-1][0]))
                asyncio.create_task(tt(text))
                if channel.guild.voice_client is None or not channel.guild.voice_client.is_playing or queue[0] != song_track:
                    break

        await loop()
        
