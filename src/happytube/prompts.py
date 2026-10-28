from collections import namedtuple

PromptDef = namedtuple("PromptDef", ["name", "version", "prompt"])

prompt_definitions = [
    PromptDef(
        name="rate_video_happiness",
        version=1,
        prompt="""
Rate the happiness of the videos provided in the list, there is always id, title, description. 
The rating should be from 1 to 5, where 1 is the least happy and 5 is the happiest. 
Please provide the answer in json format (no extra text, just the response), a list of items with `id` and `happiness`.
""",
    ),
    PromptDef(
        name="rate_video_happiness",
        version=2,
        prompt="""
Rate the happiness of the videos provided in the list, there is always id, title, description. 
The rating should be from 1 to 5, where 1 is the least happy and 5 is the happiest. 
Please provide the answer in csv format (no extra text, just the response), just 2 columns: `id` and `happiness`.
""",
    ),
    PromptDef(
        name="make_description_meaningful",
        version=1,
        prompt="""
The next text is a list of video ids in csv, there is always video_id, description.
Please determine the language of the descriptions.
Go through the video descriptions and for those in english remove all text that deosnt actually describe the video - call to subscribe, visit some page and so on (a sentence containing a link is most likely not describing the video). 
Otherwise leave the description intact, including emoticons.  

Please provide the answer in csv format (no extra text, just the response), just 3 columns: `id`, `language` and `description_improved` Please embed the `description_improved` column in quotes.
""",
    ),
]


def get_prompt(prompt_definitions, name, version):
    return next(
        p.prompt for p in prompt_definitions if p.name == name and p.version == version
    )
