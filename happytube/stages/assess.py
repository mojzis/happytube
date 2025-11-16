"""Assess stage - evaluates video happiness using Claude AI."""

import csv
import io
import os
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any

from anthropic import Anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from happytube.models.markdown import MarkdownFile
from happytube.prompts import get_prompt, prompt_definitions
from happytube.stages.base import Stage

console = Console()


class AssessStage(Stage):
    """Assesses video happiness scores using Claude AI."""

    def __init__(
        self,
        prompt_name: str = "rate_video_happiness",
        prompt_version: int = 2,
        model: str = "claude-3-opus-20240229",
        max_tokens: int = 4096,
    ):
        """Initialize AssessStage.

        Args:
            prompt_name: Name of the prompt to use
            prompt_version: Version of the prompt
            model: Claude model to use
            max_tokens: Maximum tokens for Claude response
        """
        super().__init__("assess")
        self.prompt_name = prompt_name
        self.prompt_version = prompt_version
        self.model = model
        self.max_tokens = max_tokens
        self.client = None

    def _ensure_client(self) -> Anthropic:
        """Ensure Anthropic client is initialized."""
        if self.client is None:
            load_dotenv()
            self.client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        return self.client

    def _load_videos_from_fetch(self, target_date: date) -> list[MarkdownFile]:
        """Load videos from fetch stage.

        Args:
            target_date: Date to load videos for

        Returns:
            List of MarkdownFile objects
        """
        fetch_dir = Path("stages") / "fetch" / target_date.strftime("%Y-%m-%d")

        if not fetch_dir.exists():
            return []

        videos = []
        for md_path in sorted(fetch_dir.glob("video_*.md")):
            try:
                md_file = MarkdownFile.load(md_path)
                videos.append(md_file)
            except Exception as e:
                console.print(
                    f"[yellow]⚠ Error loading {md_path.name}: {str(e)}[/yellow]"
                )

        return videos

    def _prepare_csv_for_claude(self, videos: list[MarkdownFile]) -> str:
        """Prepare CSV format for Claude API.

        Args:
            videos: List of MarkdownFile objects

        Returns:
            CSV string with video_id, title, description
        """
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)
        writer.writerow(["video_id", "title", "description"])

        for video in videos:
            fm = video.frontmatter
            # Get first 500 chars of description from content
            description = (
                video.content.split("\n\n", 1)[1] if "\n\n" in video.content else ""
            )
            description = description[:500]  # Limit description length

            writer.writerow([fm.get("video_id", ""), fm.get("title", ""), description])

        return output.getvalue()

    def _parse_claude_response(self, response_text: str) -> Dict[str, Dict[str, Any]]:
        """Parse Claude's CSV response.

        Args:
            response_text: CSV response from Claude

        Returns:
            Dictionary mapping video_id to {happiness, reasoning}
        """
        results = {}
        try:
            # Parse CSV response
            reader = csv.DictReader(io.StringIO(response_text))
            for row in reader:
                video_id = row.get("id", row.get("video_id", ""))
                happiness = row.get("happiness", "")
                # Try to parse happiness as int
                try:
                    happiness_score = int(happiness)
                except (ValueError, TypeError):
                    happiness_score = 0

                results[video_id] = {
                    "happiness_score": happiness_score,
                    "happiness_reasoning": row.get("reasoning", ""),
                }
        except Exception as e:
            console.print(f"[red]✗ Error parsing Claude response: {str(e)}[/red]")

        return results

    async def run(self, target_date: date) -> Dict[str, Any]:
        """Assess video happiness and update markdown files.

        Args:
            target_date: Date for which to assess videos

        Returns:
            Dictionary containing execution statistics
        """
        stage_dir = self.ensure_stage_dir(target_date)

        console.print(
            f"[bold blue]🎯 Assessing videos for {target_date.strftime('%Y-%m-%d')}...[/bold blue]"
        )

        try:
            # Load videos from fetch stage
            videos = self._load_videos_from_fetch(target_date)

            if not videos:
                console.print("[yellow]⚠ No videos found in fetch stage[/yellow]")
                return {
                    "assessed_videos": 0,
                    "errors": 0,
                    "message": "No videos to assess",
                    "date": target_date.strftime("%Y-%m-%d"),
                }

            console.print(
                f"[green]✓ Loaded {len(videos)} videos from fetch stage[/green]"
            )

            # Prepare CSV for Claude
            csv_content = self._prepare_csv_for_claude(videos)

            # Get prompt
            prompt = get_prompt(
                prompt_definitions, self.prompt_name, self.prompt_version
            )

            # Call Claude API
            client = self._ensure_client()

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "Calling Claude API for happiness assessment...", total=None
                )

                message = {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "text", "text": csv_content},
                    ],
                }

                response = client.messages.create(
                    model=self.model,
                    messages=[message],
                    max_tokens=self.max_tokens,
                )

                progress.update(task, completed=True)

            # Extract text from response
            response_text = response.content[0].text if response.content else ""

            console.print("[green]✓ Received response from Claude[/green]")

            # Parse response
            assessment_results = self._parse_claude_response(response_text)

            # Save assessed videos
            assessed_count = 0
            errors = []

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Saving assessed videos...", total=len(videos))

                for video in videos:
                    try:
                        video_id = video.frontmatter.get("video_id", "")
                        assessment = assessment_results.get(video_id, {})

                        # Update frontmatter
                        video.update_frontmatter(
                            {
                                "stage": "assessed",
                                "assessed_at": datetime.utcnow().isoformat() + "Z",
                                "happiness_score": assessment.get("happiness_score", 0),
                                "happiness_reasoning": assessment.get(
                                    "happiness_reasoning", ""
                                ),
                                "prompt_name": self.prompt_name,
                                "prompt_version": self.prompt_version,
                            }
                        )

                        # Save to assess stage
                        output_path = stage_dir / f"video_{video_id}.md"
                        video.save(output_path)
                        assessed_count += 1

                    except Exception as e:
                        error_msg = f"Error saving assessed video {video_id}: {str(e)}"
                        errors.append(error_msg)
                        console.print(f"[red]✗ {error_msg}[/red]")

                    progress.update(task, advance=1)

            if errors:
                console.print(f"[yellow]⚠ Completed with {len(errors)} errors[/yellow]")
            else:
                console.print(
                    f"[green]✓ Successfully assessed {assessed_count} videos[/green]"
                )

            # Calculate stats
            happiness_scores = [
                r["happiness_score"]
                for r in assessment_results.values()
                if r.get("happiness_score", 0) > 0
            ]
            avg_happiness = (
                sum(happiness_scores) / len(happiness_scores) if happiness_scores else 0
            )

            return {
                "assessed_videos": assessed_count,
                "errors": len(errors),
                "avg_happiness": round(avg_happiness, 2),
                "date": target_date.strftime("%Y-%m-%d"),
                "stage_dir": str(stage_dir),
            }

        except Exception as e:
            error_msg = f"Fatal error in AssessStage: {str(e)}"
            console.print(f"[red]✗ {error_msg}[/red]")
            return {
                "assessed_videos": 0,
                "errors": 1,
                "error_message": error_msg,
                "date": target_date.strftime("%Y-%m-%d"),
            }
