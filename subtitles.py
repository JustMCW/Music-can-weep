from urllib.request import urlopen

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
    def extract_subtitles(self,subtitles_list:list, language:str)->list:
        language_catergory = subtitles_list.get(language)
        if not language_catergory:
            language_catergory = list(subtitles_list.values())[0]
        subtitles_url = language_catergory[4]["url"]
        subtitles_file = urlopen(subtitles_url)
        subtitles = []
        is_complex = False
        for line in subtitles_file:
            if line == "\n".encode('utf-8'): continue
            line = line.decode('utf-8')
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
                    if line in subtitles[-1]:
                        continue
            subtitles.append(line)
        subtitles_file.close()
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
        if len(full) > 1: await channel.send(full)