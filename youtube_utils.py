
import re,json,requests
from typing import List
from bs4 import BeautifulSoup
url = "https://www.youtube.com/watch?v=LtrB_8CejUA"

class YoutubeVideo:
    """Provide most attributes a song track.
    It is returned by functions in `youtube_utils.py`"""
    def __init__(
        self,
        title     : str,
        videoId   : str,
        length    : str = "",
        thumbnail : str = "",
    ) -> None:
        self.title = title
        self.videoId = videoId
        self.url = f"https://www.youtube.com/watch?v={self.videoId}"
        self.length = length
        self.thumbnail = thumbnail

def search_from_youtube(query:str, ResultLengthLimit:int=5,DurationLimit:int=3*3600) -> List[YoutubeVideo]:
    """
    Search youtube videos with a given string.
    Returns a list of search result which the item contains the title, duration, channel etc.
    """

    #Send the request and grab the html text
    r = requests.get(f"https://www.youtube.com/results?search_query={'+'.join(word for word in query.split())}")
    htmlSoup = BeautifulSoup(r.text, features="html5lib")

    #Fliter the html soup ( get rid of other elements such as the search bar and side bar )
    scripts = [s for s in htmlSoup.find_all("script") if "videoRenderer" in str(s)][0]

    #Find the data we need among the scripts, and load it into json 
    json_data = json.loads(re.search('var ytInitialData = (.+)[,;]{1}',str(scripts)).group(1))

    #The Path to the search results
    query_list = json_data["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"]\
                        ["sectionListRenderer"]["contents"]
    query_list : list = query_list[len(query_list)-2]["itemSectionRenderer"]["contents"] 
    
    #Filters items in the search result
    final_list = []
    for item in query_list:
        video : dict = item.get("videoRenderer")
        if video and video.get("lengthText"): #Remove channels / playlist / live stream (live has no time length)
            longText = video["lengthText"]["accessibility"]["accessibilityData"]["label"]
            if "hours" in longText:
                #Remove video with 3+ hours duration
                if int(re.search(r"(.*) hours", longText).group(1)) > DurationLimit: 
                    continue
            final_list.append(YoutubeVideo( title   = video["title"]["runs"][0]["text"],
                                            videoId = video["videoId"],
                                            length  = video["lengthText"]["simpleText"],
                                            ))
            #title = video["title"]["runs"][0]["text"]
            #length = video["lengthText"]["simpleText"]
            #Result length
            if len(final_list) >= ResultLengthLimit: 
                break

    return final_list 

def get_recommendation(url) -> List[YoutubeVideo]:
    r = requests.get(url)
    soup = BeautifulSoup(r.text, features="html5lib")

    script =[s for s in soup.findAll("script") if "var ytInitialData = " in str(s)][0]
    json_data = json.loads(re.search('var ytInitialData = (.+)[,;]{1}',str(script)).group(1))

    results : list = json_data["contents"]["twoColumnWatchNextResults"]["secondaryResults"]["secondaryResults"]["results"]
    return_result = []
    for item in results:
        item = item.get("compactVideoRenderer")
        if not item: continue
        try:
            return_result.append(YoutubeVideo(  title   = item["title"]["simpleText"],
                                                videoId = item["videoId"],
                                                # length  = item["lengthText"]["simpleText"],
                                                thumbnail = item["thumbnail"]["thumbnails"][-1]["url"]))
        except KeyError as ke:
            print(ke)
            print(item)
    return return_result

def test(q):
    url = search_from_youtube(q)[0].url
    print(url)
    #ytInitialPlayerResponse
    r = requests.get(url)
    soup = BeautifulSoup(r.text, features="html5lib")

    script =[s for s in soup.findAll("script") if "var ytInitialPlayerResponse = " in str(s)][0]
    json_data = json.loads(re.search('var ytInitialPlayerResponse = (.+)[,;]{1}',str(script)).group(1))
    # with open("new3.json","w") as f:
    #     json.dump(json_data,f,indent=4)
    adptfmts = json_data.get("streamingData").get("adaptiveFormats")
    good_fmts = []
    print(len(adptfmts))
    for fmt in adptfmts:
        print(fmt.get("mimeType"))
        if fmt.get("mimeType") == "audio/webm; codecs=\"opus\"":
            good_fmts.append(fmt)
    print(good_fmts[0])
    return good_fmts[-1]["url"]

if __name__ == "__main__":
    print(test("neko hacker home sweet home"))
    # print(get_recommendation("https://www.youtube.com/watch?v=BnkhBwzBqlQ")[1].title)