import csv
import html
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
import requests

from happytube.utils import determine_text_script


@dataclass
class YtQuery:
    name: str = None
    url: str = None
    params: dict = field(default_factory=dict)
    data: list = field(default_factory=list)
    variant: str = "def"
    key: str | None = None

    def __post_init__(self):
        if self.key is None:
            self.key = os.getenv("YTKEY")
        self.params["key"] = self.key

    def get(self):
        response = requests.get(self.url, params=self.params)
        if response.status_code == 200:
            self.data = response.json()["items"]
        else:
            logging.error(f"Error: {response.status_code}")

    def store_locally(self):
        current_time = datetime.now().strftime("%Y-%m-%d_%H-%M")
        dir = f"data/fetched/{self.name}"
        os.makedirs(dir, exist_ok=True)
        file_path = f"{dir}/{current_time}_{self.variant}.json"
        with open(file_path, "w") as f:
            json.dump(self.data, f, indent=4)
        return file_path

    def set_param(self, key, value):
        self.params[key] = value


@dataclass
class Search(YtQuery):
    def __post_init__(self):
        self.name = "search"
        self.url = "https://www.googleapis.com/youtube/v3/search"
        self.params = {
            "part": "snippet",
            "maxResults": 50,
            "type": "video",
            # "channelId": "UCwmZiChSryoWQCZMIQezgTg",  # "bbcearth",
            "safeSearch": "strict",
            "order": "viewCount",  # "rating", relevance
            "regionCode": "CZ",
            "videoEmbeddable": True,
            "relevanceLanguage": "en",
            "videoDuration": "medium",  # "short", "medium", "long"
            "videoDimension": "2d",  # "3d", "any"
            "videoCategoryId": 15,
        }

    def get_df(self):
        data = pd.DataFrame([get_search_data(r) for r in self.data])
        data.columns = [camel_to_snake(col) for col in data.columns]
        out = data.assign(
            original_title=lambda x: x["title"],
            title=lambda x: x["title"].map(html.unescape),
            script=data["title"].apply(determine_text_script),
        )

        # ['publishedAt', 'channelId', 'title', 'description', 'thumbnails','channelTitle', 'liveBroadcastContent', 'publishTime', 'video_id']
        return out[
            [
                "video_id",
                "title",
                "description",
                "channel_title",
                "published_at",
                "thumbnails",
                "channel_id",
                "script",
            ]
        ]

    def get_list_for_claude(self):
        return self.get_df()[["video_id", "title", "description"]].to_dict(
            orient="records"
        )

    def get_csv(self, colummn_list: list | None = None):
        colummn_list = colummn_list or ["video_id", "title", "description"]
        data = self.get_df().loc[lambda x: x["script"] == "LATIN"][colummn_list]
        out = data.to_csv(index=False, quoting=csv.QUOTE_ALL)
        return out


@dataclass
class Videos(YtQuery):
    def __post_init__(self):
        self.name = "videos"
        self.url = "https://www.googleapis.com/youtube/v3/videos"
        self.params = {
            "part": "contentDetails,id,player,snippet,statistics,topicDetails",
            "maxResults": 50,
            "chart": "mostPopular",
            # "regionCode": "CZ",
            "videoCategoryId": 15,
        }


def get_search_data(row):
    out = row["snippet"]
    out["video_id"] = row["id"]["videoId"]
    return out


def camel_to_snake(name):
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
