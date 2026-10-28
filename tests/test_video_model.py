import logging

import pandas as pd

from happytube.models.markdown import MarkdownFile
from happytube.models.video import Video
from happytube.utils import today_local

_GOOD = {
    "video_id": "good",
    "title": "Calm river",
    "channel": "Nature",
    "fetched_at": "2026-01-01T10:00:00Z",
    "stage": "assessed",
    "happiness_score": 4,
}


def test_df_from_stage_dir_skips_bad_files_and_round_trips_parquet(
    tmp_path, monkeypatch, caplog
):
    monkeypatch.chdir(tmp_path)
    day_dir = tmp_path / "stages" / "assess" / f"{today_local():%Y-%m-%d}"
    day_dir.mkdir(parents=True)
    MarkdownFile(_GOOD, "body").save(day_dir / "video_good.md")
    MarkdownFile({**_GOOD, "video_id": "loud", "happiness_score": 9}, "body").save(
        day_dir / "video_loud.md"
    )
    (day_dir / "video_broken.md").write_text("---\ntitle: [unclosed\n---\nbody\n")

    with caplog.at_level(logging.WARNING, logger="happytube.models.video"):
        df = Video.df_from_stage_dir("assess", days_back=1)

    assert df["video_id"].tolist() == ["good"]
    skipped = sorted(r.args[0].name for r in caplog.records if r.args)
    assert skipped == ["video_broken.md", "video_loud.md"]

    out = tmp_path / "out.parquet"
    Video.to_parquet(df, out)
    back = pd.read_parquet(out)
    # pyarrow returns its own UTC tzinfo object; same instants, same dtype string.
    assert str(back["fetched_at"].dtype) == "datetime64[ns, UTC]"
    pd.testing.assert_frame_equal(back, df, check_dtype=False)
    assert Video.model_validate(back.iloc[0].to_dict()).video_id == "good"
