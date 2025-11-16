"""Report stage - generates HTML reports and exports analytics."""

from datetime import date
from pathlib import Path
from typing import Dict, Any, List

from jinja2 import Environment, FileSystemLoader
from rich.console import Console

from happytube.models.markdown import MarkdownFile
from happytube.models.video import Video
from happytube.stages.base import Stage

console = Console()


class ReportStage(Stage):
    """Generates daily HTML reports and exports analytics."""

    def __init__(self, template_dir: Path = Path("templates")):
        """Initialize ReportStage.

        Args:
            template_dir: Directory containing Jinja2 templates
        """
        super().__init__("report")
        self.template_dir = template_dir
        # Create Jinja2 environment
        if template_dir.exists():
            self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        else:
            self.env = None

    def _load_enhanced_videos(self, target_date: date) -> List[Dict[str, Any]]:
        """Load all enhanced videos for the target date.

        Args:
            target_date: Date to load videos for

        Returns:
            List of video dictionaries with frontmatter data
        """
        enhance_dir = Path("stages") / "enhance" / target_date.strftime("%Y-%m-%d")

        if not enhance_dir.exists():
            return []

        videos = []
        for md_path in sorted(enhance_dir.glob("video_*.md")):
            try:
                md_file = MarkdownFile.load(md_path)
                # Combine frontmatter with content
                video_data = md_file.frontmatter.copy()
                video_data["content"] = md_file.content
                videos.append(video_data)
            except Exception as e:
                console.print(
                    f"[yellow]⚠ Error loading {md_path.name}: {str(e)}[/yellow]"
                )

        # Sort by happiness score (highest first)
        videos.sort(key=lambda v: v.get("happiness_score", 0), reverse=True)

        return videos

    def _export_parquet(self, target_date: date, days_back: int = 7) -> None:
        """Export stage data to Parquet for analytics.

        Uses the Video model's df_from_stage_dir and to_parquet methods.

        Args:
            target_date: Target date
            days_back: Number of days to look back
        """
        for stage_name in ["fetch", "assess", "enhance"]:
            try:
                # Use Video model's method to load data
                df = Video.df_from_stage_dir(stage_name, days_back=days_back)

                if not df.empty:
                    output_dir = Path("parquet") / stage_name / "by-run-date"
                    output_file = (
                        output_dir
                        / f"{target_date.strftime('%Y-%m-%d')}_last_{days_back}_days.parquet"
                    )

                    # Use Video model's method to export
                    Video.to_parquet(df, output_file)

                    console.print(
                        f"[green]✓ Exported {len(df)} records to {output_file}[/green]"
                    )
            except Exception as e:
                console.print(
                    f"[yellow]⚠ Error exporting {stage_name} to parquet: {str(e)}[/yellow]"
                )

    async def run(self, target_date: date) -> Dict[str, Any]:
        """Generate report for the date.

        Args:
            target_date: Date for which to generate report

        Returns:
            Dictionary containing execution statistics
        """
        console.print(
            f"[bold blue]📊 Generating report for {target_date.strftime('%Y-%m-%d')}...[/bold blue]"
        )

        try:
            # Load enhanced videos
            videos = self._load_enhanced_videos(target_date)

            if not videos:
                console.print("[yellow]⚠ No enhanced videos found[/yellow]")
                return {
                    "videos_reported": 0,
                    "message": "No enhanced videos found",
                    "date": target_date.strftime("%Y-%m-%d"),
                }

            console.print(f"[green]✓ Loaded {len(videos)} enhanced videos[/green]")

            # Calculate statistics
            happiness_scores = [
                v.get("happiness_score", 0)
                for v in videos
                if v.get("happiness_score", 0) > 0
            ]
            avg_happiness = (
                sum(happiness_scores) / len(happiness_scores) if happiness_scores else 0
            )

            # Generate HTML report
            if self.env is None:
                console.print(
                    "[yellow]⚠ Template directory not found, skipping HTML generation[/yellow]"
                )
                report_path = None
            else:
                try:
                    template = self.env.get_template("daily_report.html")
                    html = template.render(
                        date=target_date.strftime("%Y-%m-%d"),
                        videos=videos,
                        total_count=len(videos),
                        avg_happiness=avg_happiness,
                    )

                    # Save report
                    report_path = (
                        self.stage_path / f"{target_date.strftime('%Y-%m-%d')}.html"
                    )
                    report_path.parent.mkdir(parents=True, exist_ok=True)
                    report_path.write_text(html, encoding="utf-8")

                    console.print(
                        f"[green]✓ Generated HTML report: {report_path}[/green]"
                    )
                except Exception as e:
                    console.print(
                        f"[yellow]⚠ Error generating HTML report: {str(e)}[/yellow]"
                    )
                    report_path = None

            # Export to parquet for analytics
            console.print("[blue]Exporting to Parquet...[/blue]")
            self._export_parquet(target_date)

            return {
                "videos_reported": len(videos),
                "avg_happiness": round(avg_happiness, 2),
                "report_path": str(report_path) if report_path else None,
                "date": target_date.strftime("%Y-%m-%d"),
            }

        except Exception as e:
            error_msg = f"Fatal error in ReportStage: {str(e)}"
            console.print(f"[red]✗ {error_msg}[/red]")
            return {
                "videos_reported": 0,
                "errors": 1,
                "error_message": error_msg,
                "date": target_date.strftime("%Y-%m-%d"),
            }
