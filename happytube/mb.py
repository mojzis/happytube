import marimo

__generated_with = "0.9.14"
app = marimo.App()


@app.cell
def __(Search, ytkey):
    ls = Search()
    ls.set_param("key",ytkey)
    ls.set_param("videoDuration","long")
    ls.get()
    return (ls,)


@app.cell
def __(Search, ytkey):
    s = Search()
    s.set_param("key",ytkey)
    s.get()
    return (s,)


@app.cell
def __(ls):
    ls.data
    return


@app.cell
def __(ls):
    ls.get_df()
    return


@app.cell
def __(ls):
    ls.get_csv()
    return


@app.cell
def __():
    return


@app.cell
def __(happiness, ls):
    happy_videos = ls.get_df().merge(happiness, on="video_id")
    happy_videos.sort_values("happiness", ascending=False)
    return (happy_videos,)


@app.cell
def __(StringIO, pd, resp):

    happiness = pd.read_csv(StringIO(resp.content[0].text))
    happiness
    return (happiness,)


@app.cell
def __(better_descriptions):
    better_descriptions.content[0].text

    return


@app.cell
def __(StringIO, better_descriptions, pd):
    bd = pd.read_csv(StringIO(better_descriptions.content[0].text),on_bad_lines="warn")
    bd
    return (bd,)


@app.cell
def __(cl, do_with_videos, happy_videos, prompt_definitions):
    videos_to_improve = happy_videos.loc[lambda x: x["happiness"] <= 3]
    csv = videos_to_improve[["video_id","description"]].to_csv(index=False, quoting=1)
    better_descriptions =  do_with_videos(cl,csv,prompt_definitions,prompt_name="make_description_meaningful",prompt_version=1)
    better_descriptions
    return better_descriptions, csv, videos_to_improve


@app.cell
def __(cl, ls, prompt_definitions, range_video_happiness):
    resp = range_video_happiness(cl,ls.get_csv(),prompt_definitions)
    resp
    return (resp,)


@app.cell
def __(create_client):
    cl =create_client()
    return (cl,)


@app.cell
def __():
    from io import StringIO
    return (StringIO,)


@app.cell
def __():
    from happytube.prompts import prompt_definitions
    return (prompt_definitions,)


@app.cell
def __():
    from happytube.claude import range_video_happiness, create_client, do_with_videos
    return create_client, do_with_videos, range_video_happiness


@app.cell
def __():
    import marimo as mo
    from dotenv import load_dotenv
    import os
    import pandas as pd

    _ = load_dotenv()

    ytkey = os.getenv("YTKEY")

    url_search = "https://www.googleapis.com/youtube/v3/search"
    url_categ = "https://www.googleapis.com/youtube/v3/videoCategories"
    params_categ = {"part": "snippet", "regionCode": "CZ", "key": ytkey}
    from happytube.videos import YtQuery, Videos, Search
    return (
        Search,
        Videos,
        YtQuery,
        load_dotenv,
        mo,
        os,
        params_categ,
        pd,
        url_categ,
        url_search,
        ytkey,
    )


if __name__ == "__main__":
    app.run()
