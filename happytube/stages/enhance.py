"""Enhance stage - improves video descriptions using Claude AI."""

import os
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Any

from anthropic import Anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from happytube.models.markdown import MarkdownFile
from happytube.stages.base import Stage

console = Console()


class EnhanceStage(Stage):
    """Enhances video descriptions using Claude AI."""

    def __init__(
        self,
        happiness_threshold: int = 3,
        prompt_name: str = "make_description_meaningful",
        prompt_version: int = 1,
        model: str = "claude-3-opus-20240229",
        max_tokens: int = 2048,
    ):
        """Initialize EnhanceStage.

        Args:
            happiness_threshold: Minimum happiness score to enhance (default: 3)
            prompt_name: Name of the prompt to use
            prompt_version: Version of the prompt
            model: Claude model to use
            max_tokens: Maximum tokens for Claude response
        """
        super().__init__("enhance")
        self.happiness_threshold = happiness_threshold
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

    def _load_videos_from_assess(self, target_date: date) -> list[MarkdownFile]:
        """Load videos from assess stage that meet happiness threshold.

        Args:
            target_date: Date to load videos for

        Returns:
            List of MarkdownFile objects with happiness >= threshold
        """
        assess_dir = Path("stages") / "assess" / target_date.strftime("%Y-%m-%d")

        if not assess_dir.exists():
            return []

        videos = []
        for md_path in sorted(assess_dir.glob("video_*.md")):
            try:
                md_file = MarkdownFile.load(md_path)
                happiness_score = md_file.frontmatter.get("happiness_score", 0)

                # Only include videos that meet threshold
                if happiness_score >= self.happiness_threshold:
                    videos.append(md_file)

            except Exception as e:
                console.print(
                    f"[yellow]⚠ Error loading {md_path.name}: {str(e)}[/yellow]"
                )

        return videos

    def _enhance_description_simple(self, title: str, description: str) -> str:
        """Enhance a single video description using Claude.

        Args:
            title: Video title
            description: Original description

        Returns:
            Enhanced description
        """
        client = self._ensure_client()

        prompt = f"""Improve this YouTube video description by removing:
- Clickbait language
- "Like and subscribe" spam
- Excessive links
- Overly promotional content
- Social media handles

Keep the core information that describes what the video is about.
Return ONLY the enhanced description, nothing else.

Title: {title}
Description: {description}

Enhanced Description:"""

        try:
            response = client.messages.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": prompt}],
                    }
                ],
                max_tokens=self.max_tokens,
            )

            enhanced = response.content[0].text if response.content else description
            return enhanced.strip()

        except Exception as e:
            console.print(f"[yellow]⚠ Error enhancing description: {str(e)}[/yellow]")
            return description

    async def run(self, target_date: date) -> Dict[str, Any]:
        """Enhance video descriptions and update markdown files.

        Args:
            target_date: Date for which to enhance videos

        Returns:
            Dictionary containing execution statistics
        """
        stage_dir = self.ensure_stage_dir(target_date)

        console.print(
            f"[bold blue]✨ Enhancing videos for {target_date.strftime('%Y-%m-%d')}...[/bold blue]"
        )

        try:
            # Load videos from assess stage
            videos = self._load_videos_from_assess(target_date)

            if not videos:
                console.print(
                    f"[yellow]⚠ No videos with happiness >= {self.happiness_threshold} found[/yellow]"
                )
                return {
                    "enhanced_videos": 0,
                    "errors": 0,
                    "message": f"No videos with happiness >= {self.happiness_threshold}",
                    "date": target_date.strftime("%Y-%m-%d"),
                }

            console.print(
                f"[green]✓ Loaded {len(videos)} videos from assess stage (happiness >= {self.happiness_threshold})[/green]"
            )

            # Enhance each video
            enhanced_count = 0
            errors = []

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "Enhancing video descriptions...", total=len(videos)
                )

                for video in videos:
                    try:
                        video_id = video.frontmatter.get("video_id", "")
                        title = video.frontmatter.get("title", "")

                        # Extract description from content
                        description = (
                            video.content.split("\n\n", 1)[1]
                            if "\n\n" in video.content
                            else ""
                        )

                        # Enhance description using Claude
                        enhanced_description = self._enhance_description_simple(
                            title, description
                        )

                        # Update frontmatter
                        video.update_frontmatter(
                            {
                                "stage": "enhanced",
                                "enhanced_at": datetime.utcnow().isoformat() + "Z",
                                "enhanced_description": enhanced_description,
                            }
                        )

                        # Update content with enhanced description
                        video.content = f"# {title}\n\n{enhanced_description}"

                        # Save to enhance stage
                        output_path = stage_dir / f"video_{video_id}.md"
                        video.save(output_path)
                        enhanced_count += 1

                    except Exception as e:
                        error_msg = f"Error enhancing video {video.frontmatter.get('video_id', 'unknown')}: {str(e)}"
                        errors.append(error_msg)
                        console.print(f"[red]✗ {error_msg}[/red]")

                    progress.update(task, advance=1)

            if errors:
                console.print(f"[yellow]⚠ Completed with {len(errors)} errors[/yellow]")
            else:
                console.print(
                    f"[green]✓ Successfully enhanced {enhanced_count} videos[/green]"
                )

            return {
                "enhanced_videos": enhanced_count,
                "errors": len(errors),
                "date": target_date.strftime("%Y-%m-%d"),
                "stage_dir": str(stage_dir),
            }

        except Exception as e:
            error_msg = f"Fatal error in EnhanceStage: {str(e)}"
            console.print(f"[red]✗ {error_msg}[/red]")
            return {
                "enhanced_videos": 0,
                "errors": 1,
                "error_message": error_msg,
                "date": target_date.strftime("%Y-%m-%d"),
            }
