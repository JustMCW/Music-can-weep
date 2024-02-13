
import re
import json
import requests

# from functools import cache
from typing import List,TypedDict,Tuple,Optional
from bs4    import BeautifulSoup,element
from dataclasses import dataclass

class URLMatch(TypedDict):
    protocol : Optional[str]
    subdomain : Optional[str]
    domain : Optional[str]
    top_level_domain : Optional[str]
    directory : Optional[str]
    page : Optional[str]


def url_matcher(url: str) -> Optional[URLMatch]:
    """return a match for a url, None for no matches"""
    matches = re.search(r"(https|HTTP)?:?/?/?(\w+\.)?(.+)\.(\w+)/([^/]+)?/?(.+)?", url)

    if not matches:
        return None

    protocol, subdomain, domain, top_level_domain, directory, page = matches.groups()

    if not page:
        page = directory
        directory = None
    
    # removing the dot
    if subdomain and subdomain[-1] == ".":
        subdomain = subdomain[:-1]

    return  {
        "protocol" : protocol,
        "subdomain" : subdomain,
        "domain" : domain,
        "top_level_domain" : top_level_domain,
        "directory" : directory,
        "page" : page,
    }

@dataclass
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

def extract_yt_url_from(string : str) -> Optional[str]:
    matches = re.findall(r"(https|HTTP)://(youtu\.be|www.youtube.com)(/shorts)?/(watch\?v=)?([A-Za-z0-9\-_]{11})",string)
    if matches:
        return "https://www.youtube.com/watch?v="+matches[0][4]
    return None

def run_test():
    example_link = "https://www.youtube.com/watch?v=9NNy39vj-Wo"
    assert extract_yt_url_from("ez")==None
    assert extract_yt_url_from(f"pro{example_link}")== example_link
    assert extract_yt_url_from(f"<{example_link}>")==example_link
    assert extract_yt_url_from("https://www.youtube.com/watch?v=x8VYWazR5mE&ab_channel=Ayase%2FYOASOBI")=="https://www.youtube.com/watch?v=x8VYWazR5mE"

# @cache
def search_from_youtube(query:str, ResultLengthLimit:int=5,DurationLimit:int=3*3600) -> List[YoutubeVideo]:
    """
    Search youtube videos with a given string.
    Returns a list of search result which the item contains the title, duration, channel etc.
    """

    #Send the request and grab the html text
    r = requests.get(f"https://www.youtube.com/results?search_query={'+'.join(word for word in query.split())}")
    htmlSoup = BeautifulSoup(r.text, features="lxml")

    #Fliter the html soup ( getting rid of other elements such as the search bar and side bar )
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
    
        if not video:
            continue

        
        if video.get("lengthText"): #Remove channels / playlist / live stream (live has no time length)
            longText = video["lengthText"]["accessibility"]["accessibilityData"]["label"]
            if "hours" in longText:
                #Remove video with 3+ hours duration
                if int(re.search(r"(.*) hours", longText).group(1)) > DurationLimit: 
                    continue

        final_list.append(
            YoutubeVideo( 
                title   = video["title"]["runs"][0]["text"],                        
                videoId = video["videoId"],
                length  = video["lengthText"]["simpleText"] if video.get("lengthText") else "Livestream",
            )
        )
        #Result length
        if len(final_list) >= ResultLengthLimit: 
            break

    return final_list 

def get_spotify_track_title(url : str) -> str:
    r = requests.get(url)
    htmlSoup = BeautifulSoup(r.text, features="lxml")
    title_tag : element.Tag = htmlSoup.find_all("title")[0]
    return title_tag.text.replace(" | Spotify","")

pattern = re.compile(r'https://open\.spotify\.com/track/\w+')

def get_playlist_data(playlist_url) -> Tuple[str,list[str]]:
    r = requests.get(playlist_url)
    
    tracks = re.findall(
        r'https://open\.spotify\.com/track/.{22}',
        r.text,
    )
    
    soup = BeautifulSoup(r.text,features="lxml")
    title = soup.find("title").contents[0]
    return str(title),tracks


    
def get_recommendation(url) -> List[YoutubeVideo]:
    r = requests.get(url)
    soup = BeautifulSoup(r.text, features="lxml")

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
            raise
    return return_result

