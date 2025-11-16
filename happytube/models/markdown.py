"""Markdown file handling with YAML frontmatter support."""

import yaml
from pathlib import Path
from typing import Dict, Any


class MarkdownFile:
    """Represents a Markdown file with YAML frontmatter."""

    def __init__(self, frontmatter: Dict[str, Any], content: str):
        """Initialize a MarkdownFile.

        Args:
            frontmatter: Dictionary containing YAML frontmatter data
            content: The markdown content (without frontmatter)
        """
        self.frontmatter = frontmatter
        self.content = content

    @classmethod
    def load(cls, file_path: Path) -> "MarkdownFile":
        """Load a Markdown file with frontmatter.

        Args:
            file_path: Path to the markdown file

        Returns:
            MarkdownFile instance with parsed frontmatter and content
        """
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        # Split frontmatter and content
        if text.startswith("---\n"):
            parts = text.split("---\n", 2)
            frontmatter = yaml.safe_load(parts[1])
            content = parts[2].strip()
        else:
            frontmatter = {}
            content = text

        return cls(frontmatter, content)

    def save(self, file_path: Path) -> None:
        """Save the Markdown file with frontmatter.

        Args:
            file_path: Path where the markdown file should be saved
        """
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.to_string())

    def to_string(self) -> str:
        """Convert to string format with frontmatter.

        Returns:
            Complete markdown file content with frontmatter
        """
        yaml_str = yaml.dump(
            self.frontmatter, default_flow_style=False, sort_keys=False
        )
        return f"---\n{yaml_str}---\n\n{self.content}"

    def update_frontmatter(self, updates: Dict[str, Any]) -> None:
        """Update frontmatter with new values.

        Args:
            updates: Dictionary of values to update in frontmatter
        """
        self.frontmatter.update(updates)
