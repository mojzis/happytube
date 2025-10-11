# ruff: noqa
get_ipython().run_line_magic("load_ext", "autoreload")
get_ipython().run_line_magic("autoreload", "2")


import os
import requests
from dotenv import load_dotenv
import json


from happytube.videos import YtQuery, Videos

_ = load_dotenv()

ytkey = os.getenv("YTKEY")


url_search = "https://www.googleapis.com/youtube/v3/search"
url_categ = "https://www.googleapis.com/youtube/v3/videoCategories"
params_categ = {"part": "snippet", "regionCode": "CZ", "key": ytkey}


cats_to_query = [34, 15, 10, 19, 35]
params_search = {
    "part": "snippet",
    "maxResults": 50,
    "type": "video",
    # "videoCategoryId": 15,
    "channelId": "UCwmZiChSryoWQCZMIQezgTg",  # "bbcearth",
    "key": ytkey,
    "safeSearch": "strict",
    "order": "relevance",  # "rating",
    "regionCode": "CZ",
    "videoEmbeddable": True,
    "relevanceLanguage": "en",
}
