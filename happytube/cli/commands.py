"""CLI commands for HappyTube."""

import asyncio
import sys
from datetime import date, datetime
from functools import wraps
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from happytube.config.config_manager import ConfigManager
from happytube.config.settings import get_settings
from happytube.stages.assess import AssessStage
from happytube.stages.enhance import EnhanceStage
from happytube.stages.fetch import FetchStage
from happytube.stages.report import ReportStage

console = Console()


def require_credentials(f):
    """Decorator to validate credentials before running a command."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        validate_credentials()
        return f(*args, **kwargs)

    return wrapper


def parse_date(date_str: str | None) -> date:
    """Parse date string or return today's date.

    Args:
        date_str: Date string in YYYY-MM-DD format or None

    Returns:
        Parsed date object or today's date
    """
    if date_str is None:
        return date.today()

    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        console.print(
            f"[red]✗ Invalid date format: {date_str}. Use YYYY-MM-DD format.[/red]"
        )
        sys.exit(1)


def validate_credentials():
    """Validate that required API credentials are configured."""
    try:
        settings = get_settings()
        if not settings.has_all_credentials:
            console.print(
                Panel(
                    "[red]Missing required API credentials![/red]\n\n"
                    "Please ensure the following environment variables are set:\n"
                    "  • YTKEY (YouTube Data API key)\n"
                    "  • ANTHROPIC_API_KEY (Claude API key)\n\n"
                    "You can set them in a .env file in the project root.",
                    title="Configuration Error",
                    border_style="red",
                )
            )
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Configuration error: {str(e)}[/red]")
        sys.exit(1)


@click.group()
@click.version_option(version="0.0.1", prog_name="happytube")
@click.pass_context
def cli(ctx):
    """HappyTube - YouTube happiness analyzer.

    Fetches videos from YouTube, assesses their happiness levels using Claude AI,
    enhances descriptions for happy videos, and generates reports.
    """
    # Skip validation for help command
    if ctx.invoked_subcommand is None:
        return


@cli.command()
@click.option(
    "--category",
    default="Music",
    help="YouTube category to search (e.g., Music, Education, Entertainment)",
)
@click.option(
    "--max-videos",
    default=50,
    type=int,
    help="Maximum number of videos to fetch",
)
@click.option(
    "--date",
    help="Target date in YYYY-MM-DD format (defaults to today)",
)
@require_credentials
def fetch(category: str, max_videos: int, date: str | None):
    """Fetch videos from YouTube and store as markdown files.

    Searches YouTube for videos in the specified category and saves them
    as markdown files with YAML frontmatter in the fetch stage directory.

    Example:
        happytube fetch --category Music --max-videos 50
    """
    target_date = parse_date(date)

    console.print(
        Panel(
            f"[bold]Category:[/bold] {category}\n"
            f"[bold]Max Videos:[/bold] {max_videos}\n"
            f"[bold]Date:[/bold] {target_date.strftime('%Y-%m-%d')}",
            title="🔍 Fetch Stage",
            border_style="blue",
        )
    )

    try:
        # Load YouTube config if available
        config_manager = ConfigManager()
        youtube_config = {}

        # Try to load category-specific config
        try:
            config_manager.load_all_base_configs()
            # Map category name to config key
            search_key = f"{category.lower()}_search"
            youtube_search = config_manager.get_youtube_search(search_key)
            youtube_config = youtube_search.get("params", {})
            console.print(
                f"[green]✓ Loaded YouTube search config: {search_key}[/green]"
            )
        except (FileNotFoundError, KeyError):
            console.print(
                f"[yellow]⚠ No config found for '{category}', using defaults[/yellow]"
            )

        # Create and run fetch stage
        stage = FetchStage(youtube_config=youtube_config, max_videos=max_videos)
        result = asyncio.run(stage.run(target_date))

        # Display results
        if result.get("errors", 0) > 0:
            console.print(
                f"\n[yellow]⚠ Completed with {result['errors']} error(s)[/yellow]"
            )
        else:
            console.print(
                f"\n[green bold]✓ Successfully fetched {result['new_videos']} videos![/green bold]"
            )

        console.print(f"[dim]Stage directory: {result.get('stage_dir')}[/dim]")

    except Exception as e:
        console.print(f"\n[red]✗ Fetch failed: {str(e)}[/red]")
        sys.exit(1)


@cli.command()
@click.option(
    "--date",
    help="Target date in YYYY-MM-DD format (defaults to today)",
)
@require_credentials
def assess(date: str | None):
    """Assess video happiness using Claude AI.

    Loads videos from the fetch stage, sends them to Claude AI for happiness
    assessment, and saves the results with scores in the assess stage directory.

    Example:
        happytube assess --date 2025-11-16
    """
    target_date = parse_date(date)

    console.print(
        Panel(
            f"[bold]Date:[/bold] {target_date.strftime('%Y-%m-%d')}",
            title="🎯 Assess Stage",
            border_style="blue",
        )
    )

    try:
        # Create and run assess stage
        stage = AssessStage()
        result = asyncio.run(stage.run(target_date))

        # Display results
        if result.get("errors", 0) > 0:
            console.print(
                f"\n[yellow]⚠ Completed with {result['errors']} error(s)[/yellow]"
            )
        else:
            console.print(
                f"\n[green bold]✓ Successfully assessed {result['assessed_videos']} videos![/green bold]"
            )

        if "avg_happiness" in result:
            console.print(
                f"[cyan]Average happiness score: {result['avg_happiness']}/5[/cyan]"
            )

        console.print(f"[dim]Stage directory: {result.get('stage_dir')}[/dim]")

    except Exception as e:
        console.print(f"\n[red]✗ Assess failed: {str(e)}[/red]")
        sys.exit(1)


@cli.command()
@click.option(
    "--threshold",
    default=3,
    type=int,
    help="Minimum happiness score to enhance (1-5 scale)",
)
@click.option(
    "--date",
    help="Target date in YYYY-MM-DD format (defaults to today)",
)
@require_credentials
def enhance(threshold: int, date: str | None):
    """Enhance video descriptions using Claude AI.

    Loads videos with happiness scores >= threshold from the assess stage,
    uses Claude AI to improve their descriptions, and saves the enhanced
    versions in the enhance stage directory.

    Example:
        happytube enhance --threshold 3 --date 2025-11-16
    """
    target_date = parse_date(date)

    if threshold < 1 or threshold > 5:
        console.print("[red]✗ Threshold must be between 1 and 5[/red]")
        sys.exit(1)

    console.print(
        Panel(
            f"[bold]Threshold:[/bold] {threshold}/5\n"
            f"[bold]Date:[/bold] {target_date.strftime('%Y-%m-%d')}",
            title="✨ Enhance Stage",
            border_style="blue",
        )
    )

    try:
        # Create and run enhance stage
        stage = EnhanceStage(happiness_threshold=threshold)
        result = asyncio.run(stage.run(target_date))

        # Display results
        if result.get("errors", 0) > 0:
            console.print(
                f"\n[yellow]⚠ Completed with {result['errors']} error(s)[/yellow]"
            )
        else:
            console.print(
                f"\n[green bold]✓ Successfully enhanced {result['enhanced_videos']} videos![/green bold]"
            )

        console.print(f"[dim]Stage directory: {result.get('stage_dir')}[/dim]")

    except Exception as e:
        console.print(f"\n[red]✗ Enhance failed: {str(e)}[/red]")
        sys.exit(1)


@cli.command()
@click.option(
    "--date",
    help="Target date in YYYY-MM-DD format (defaults to today)",
)
@click.option(
    "--days-back",
    default=7,
    type=int,
    help="Number of days to look back for analytics export",
)
@require_credentials
def report(date: str | None, days_back: int):
    """Generate HTML report and export analytics.

    Creates a daily HTML report summarizing enhanced videos and exports
    stage data to Parquet format for analytics.

    Example:
        happytube report --date 2025-11-16 --days-back 7
    """
    target_date = parse_date(date)

    console.print(
        Panel(
            f"[bold]Date:[/bold] {target_date.strftime('%Y-%m-%d')}\n"
            f"[bold]Days Back:[/bold] {days_back}",
            title="📊 Report Stage",
            border_style="blue",
        )
    )

    try:
        # Create and run report stage
        stage = ReportStage()
        result = asyncio.run(stage.run(target_date))

        # Display results
        if result.get("errors", 0) > 0:
            console.print(
                f"\n[yellow]⚠ Completed with {result['errors']} error(s)[/yellow]"
            )
        else:
            console.print(
                f"\n[green bold]✓ Successfully generated report for {result['videos_reported']} videos![/green bold]"
            )

        if "avg_happiness" in result:
            console.print(
                f"[cyan]Average happiness score: {result['avg_happiness']}/5[/cyan]"
            )

        if result.get("report_path"):
            console.print(f"[green]Report saved to: {result['report_path']}[/green]")

    except Exception as e:
        console.print(f"\n[red]✗ Report failed: {str(e)}[/red]")
        sys.exit(1)


@cli.command()
@click.option(
    "--category",
    default="Music",
    help="YouTube category to search",
)
@click.option(
    "--max-videos",
    default=50,
    type=int,
    help="Maximum number of videos to fetch",
)
@click.option(
    "--threshold",
    default=3,
    type=int,
    help="Minimum happiness score to enhance (1-5 scale)",
)
@click.option(
    "--date",
    help="Target date in YYYY-MM-DD format (defaults to today)",
)
@click.option(
    "--days-back",
    default=7,
    type=int,
    help="Number of days to look back for analytics export",
)
@require_credentials
def run_all(
    category: str,
    max_videos: int,
    threshold: int,
    date: str | None,
    days_back: int,
):
    """Run complete pipeline: fetch → assess → enhance → report.

    Executes all stages sequentially to process videos from YouTube through
    to final report generation.

    Example:
        happytube run-all --category Music --max-videos 50
    """
    target_date = parse_date(date)

    console.print(
        Panel(
            "[bold cyan]Starting HappyTube Pipeline[/bold cyan]\n\n"
            f"[bold]Category:[/bold] {category}\n"
            f"[bold]Max Videos:[/bold] {max_videos}\n"
            f"[bold]Happiness Threshold:[/bold] {threshold}/5\n"
            f"[bold]Date:[/bold] {target_date.strftime('%Y-%m-%d')}\n"
            f"[bold]Days Back (for analytics):[/bold] {days_back}",
            title="🚀 Run All Stages",
            border_style="green",
        )
    )

    all_results = {}

    try:
        # Stage 1: Fetch
        console.print("\n[bold blue]Stage 1/4: Fetch[/bold blue]")
        console.print("=" * 60)

        config_manager = ConfigManager()
        youtube_config = {}

        try:
            config_manager.load_all_base_configs()
            search_key = f"{category.lower()}_search"
            youtube_search = config_manager.get_youtube_search(search_key)
            youtube_config = youtube_search.get("params", {})
        except (FileNotFoundError, KeyError):
            pass

        fetch_stage = FetchStage(youtube_config=youtube_config, max_videos=max_videos)
        fetch_result = asyncio.run(fetch_stage.run(target_date))
        all_results["fetch"] = fetch_result

        if fetch_result.get("new_videos", 0) == 0:
            console.print("[yellow]⚠ No videos fetched, stopping pipeline[/yellow]")
            return

        console.print(f"[green]✓ Fetched {fetch_result['new_videos']} videos[/green]\n")

        # Stage 2: Assess
        console.print("[bold blue]Stage 2/4: Assess[/bold blue]")
        console.print("=" * 60)

        assess_stage = AssessStage()
        assess_result = asyncio.run(assess_stage.run(target_date))
        all_results["assess"] = assess_result

        if assess_result.get("assessed_videos", 0) == 0:
            console.print(
                "[yellow]⚠ No videos assessed, skipping remaining stages[/yellow]"
            )
            return

        console.print(
            f"[green]✓ Assessed {assess_result['assessed_videos']} videos "
            f"(avg: {assess_result.get('avg_happiness', 0)}/5)[/green]\n"
        )

        # Stage 3: Enhance
        console.print("[bold blue]Stage 3/4: Enhance[/bold blue]")
        console.print("=" * 60)

        enhance_stage = EnhanceStage(happiness_threshold=threshold)
        enhance_result = asyncio.run(enhance_stage.run(target_date))
        all_results["enhance"] = enhance_result

        console.print(
            f"[green]✓ Enhanced {enhance_result['enhanced_videos']} videos[/green]\n"
        )

        # Stage 4: Report
        console.print("[bold blue]Stage 4/4: Report[/bold blue]")
        console.print("=" * 60)

        report_stage = ReportStage()
        report_result = asyncio.run(report_stage.run(target_date))
        all_results["report"] = report_result

        console.print(
            f"[green]✓ Generated report for {report_result['videos_reported']} videos[/green]\n"
        )

        # Final summary
        console.print(
            Panel(
                f"[green bold]✓ Pipeline completed successfully![/green bold]\n\n"
                f"[bold]Summary:[/bold]\n"
                f"  • Fetched: {fetch_result['new_videos']} videos\n"
                f"  • Assessed: {assess_result['assessed_videos']} videos\n"
                f"  • Enhanced: {enhance_result['enhanced_videos']} videos\n"
                f"  • Reported: {report_result['videos_reported']} videos\n"
                f"  • Avg Happiness: {assess_result.get('avg_happiness', 0)}/5",
                title="🎉 Pipeline Complete",
                border_style="green",
            )
        )

        if report_result.get("report_path"):
            console.print(
                f"\n[cyan]View report at: {report_result['report_path']}[/cyan]"
            )

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠ Pipeline interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]✗ Pipeline failed: {str(e)}[/red]")
        sys.exit(1)


@cli.command()
@click.option(
    "--date",
    help="Target date in YYYY-MM-DD format (defaults to today)",
)
def status(date: str | None):
    """Show stage progress for a specific date.

    Displays a Rich table showing the number of videos in each stage
    for the specified date.

    Example:
        happytube status --date 2025-11-16
    """
    target_date = parse_date(date)

    console.print(
        Panel(
            f"[bold]Date:[/bold] {target_date.strftime('%Y-%m-%d')}",
            title="📈 Stage Status",
            border_style="blue",
        )
    )

    # Create table
    table = Table(title=f"\nStage Progress for {target_date.strftime('%Y-%m-%d')}")
    table.add_column("Stage", style="cyan", no_wrap=True)
    table.add_column("Status", style="magenta")
    table.add_column("Videos", justify="right", style="green")
    table.add_column("Directory", style="dim")

    stages = ["fetch", "assess", "enhance", "report"]
    date_str = target_date.strftime("%Y-%m-%d")

    for stage_name in stages:
        if stage_name == "report":
            # Report is a single file, not a directory of videos
            report_path = Path("stages") / "report" / f"{date_str}.html"
            if report_path.exists():
                status_str = "✓ Complete"
                count = "1 file"
                dir_str = str(report_path)
            else:
                status_str = "○ Not started"
                count = "-"
                dir_str = "-"
        else:
            stage_dir = Path("stages") / stage_name / date_str

            if stage_dir.exists():
                video_files = list(stage_dir.glob("video_*.md"))
                video_count = len(video_files)

                if video_count > 0:
                    status_str = "✓ Complete"
                    count = str(video_count)
                    dir_str = str(stage_dir)
                else:
                    status_str = "○ Empty"
                    count = "0"
                    dir_str = str(stage_dir)
            else:
                status_str = "○ Not started"
                count = "-"
                dir_str = "-"

        table.add_row(stage_name.capitalize(), status_str, count, dir_str)

    console.print(table)

    # Check for errors or warnings
    console.print(
        "\n[dim]Tip: Use 'happytube run-all' to run the complete pipeline[/dim]"
    )


if __name__ == "__main__":
    cli()
