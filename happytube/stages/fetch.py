"""Fetch stage - retrieves videos from YouTube."""

from datetime import date, datetime
from typing import Dict, Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from happytube.models.markdown import MarkdownFile
from happytube.stages.base import Stage
from happytube.videos import Search

console = Console()


class FetchStage(Stage):
    """Fetches videos from YouTube and stores as markdown files."""

    def __init__(
        self, youtube_config: Dict[str, Any] | None = None, max_videos: int = 50
    ):
        """Initialize FetchStage.

        Args:
            youtube_config: Configuration for YouTube search (optional)
            max_videos: Maximum number of videos to fetch
        """
        super().__init__("fetch")
        self.youtube_config = youtube_config or {}
        self.max_videos = max_videos

    async def run(self, target_date: date) -> Dict[str, Any]:
        """Fetch videos and save as markdown files.

        Args:
            target_date: Date for which to fetch videos

        Returns:
            Dictionary containing execution statistics
        """
        stage_dir = self.ensure_stage_dir(target_date)

        console.print(
            f"[bold blue]🔍 Fetching videos for {target_date.strftime('%Y-%m-%d')}...[/bold blue]"
        )

        try:
            # Create Search instance
            search = Search()

            # Apply custom config if provided
            for key, value in self.youtube_config.items():
                search.set_param(key, value)

            # Fetch videos from YouTube
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Fetching from YouTube API...", total=None)
                search.get()
                progress.update(task, completed=True)

            # Convert to DataFrame
            videos_df = search.get_df()

            # Limit to max_videos
            if len(videos_df) > self.max_videos:
                videos_df = videos_df.head(self.max_videos)

            console.print(f"[green]✓ Retrieved {len(videos_df)} videos[/green]")

            # Save each video as a markdown file
            saved_count = 0
            errors = []

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"Saving videos to {stage_dir}...", total=len(videos_df)
                )

                for _, row in videos_df.iterrows():
                    try:
                        # Create frontmatter
                        frontmatter = {
                            "video_id": row["video_id"],
                            "title": row["title"],
                            "channel": row.get("channel_title", ""),
                            "channel_id": row.get("channel_id", ""),
                            "published_at": row.get("published_at", ""),
                            "fetched_at": datetime.utcnow().isoformat() + "Z",
                            "stage": "fetched",
                            "script_type": row.get("script", ""),
                        }

                        # Create content (title + description)
                        content = f"# {row['title']}\n\n{row.get('description', '')}"

                        # Save as markdown file
                        md_file = MarkdownFile(frontmatter, content)
                        output_path = stage_dir / f"video_{row['video_id']}.md"
                        md_file.save(output_path)
                        saved_count += 1

                    except Exception as e:
                        error_msg = f"Error saving video {row.get('video_id', 'unknown')}: {str(e)}"
                        errors.append(error_msg)
                        console.print(f"[red]✗ {error_msg}[/red]")

                    progress.update(task, advance=1)

            if errors:
                console.print(f"[yellow]⚠ Completed with {len(errors)} errors[/yellow]")
            else:
                console.print(
                    f"[green]✓ Successfully saved {saved_count} videos[/green]"
                )

            return {
                "new_videos": saved_count,
                "errors": len(errors),
                "date": target_date.strftime("%Y-%m-%d"),
                "stage_dir": str(stage_dir),
            }

        except Exception as e:
            error_msg = f"Fatal error in FetchStage: {str(e)}"
            console.print(f"[red]✗ {error_msg}[/red]")
            return {
                "new_videos": 0,
                "errors": 1,
                "error_message": error_msg,
                "date": target_date.strftime("%Y-%m-%d"),
            }
