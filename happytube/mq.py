import asyncio
import os
from io import StringIO

import pandas as pd
from client import create_client, do_with_videos, range_video_happiness
from dotenv import load_dotenv
from search import Search


async def fetch_videos(queue):
    while True:
        _ = load_dotenv()
        ytkey = os.getenv("YTKEY")
        ls = Search()
        ls.set_param("key", ytkey)
        ls.set_param("videoDuration", "long")
        ls.get()
        await queue.put(ls)
        await asyncio.sleep(60)  # Wait for a minute before fetching new videos


async def get_multiple_items(queue, num_items):
    items = []
    for _ in range(num_items):
        item = await queue.get()
        items.append(item)
    return items


async def measure_happiness(queue_in, queue_out):
    while True:
        ls_list = await get_multiple_items(queue_in, 10)
        for ls in ls_list:
            cl = create_client()
            happiness_response = range_video_happiness(
                cl, ls.get_csv(), prompt_definitions
            )
            happiness = pd.read_csv(StringIO(happiness_response.content[0].text))
            happy_videos = ls.get_df().merge(happiness, on="video_id")
            happy_videos.sort_values("happiness", ascending=False)
            videos_to_improve = happy_videos.loc[lambda x: x["happiness"] >= 3]
            await queue_out.put(videos_to_improve)


async def improve_descriptions(queue):
    while True:
        videos_to_improve_list = await get_multiple_items(queue, 10)
        for videos_to_improve in videos_to_improve_list:
            csv = videos_to_improve[["video_id", "description"]].to_csv(
                index=False, quoting=1
            )
            cl = create_client()
            better_descriptions = do_with_videos(
                cl,
                csv,
                prompt_definitions,
                prompt_name="make_description_meaningful",
                prompt_version=1,
            )
            bd = pd.read_csv(
                StringIO(better_descriptions.content[0].text), on_bad_lines="warn"
            )
            print(bd)


async def main():
    queue1 = asyncio.Queue()
    queue2 = asyncio.Queue()
    await asyncio.gather(
        fetch_videos(queue1),
        measure_happiness(queue1, queue2),
        improve_descriptions(queue2),
    )


if __name__ == "__main__":
    asyncio.run(main())
