import os
from io import StringIO

import pandas as pd
from dotenv import load_dotenv

from happytube.claude import create_client, do_with_videos, range_video_happiness
from happytube.prompts import prompt_definitions

# from io import StringIO
from happytube.videos import Search


def main():
    _ = load_dotenv()

    ytkey = os.getenv("YTKEY")
    ls = Search()
    ls.set_param("key", ytkey)
    ls.set_param("videoDuration", "long")
    ls.get()
    # todo: store it (how ?) + log
    # todo: go through previously stored content and identify new videos

    cl = create_client()
    happiness_response = range_video_happiness(cl, ls.get_csv(), prompt_definitions)
    happiness = pd.read_csv(StringIO(happiness_response.content[0].text))

    happy_videos = ls.get_df().merge(happiness, on="video_id")
    happy_videos.sort_values("happiness", ascending=False)

    videos_to_improve = happy_videos.loc[lambda x: x["happiness"] >= 3]

    csv = videos_to_improve[["video_id", "description"]].to_csv(index=False, quoting=1)
    better_descriptions = do_with_videos(
        cl,
        csv,
        prompt_definitions,
        prompt_name="make_description_meaningful",
        prompt_version=1,
    )

    # todo: change on_bad_lines to function to log the content
    bd = pd.read_csv(StringIO(better_descriptions.content[0].text), on_bad_lines="warn")
