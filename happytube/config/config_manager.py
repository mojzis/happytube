"""Configuration manager for loading YAML configuration files."""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class ConfigManager:
    """Manages loading and accessing YAML configuration files."""

    def __init__(self, base_path: Path = Path("config/base")):
        """Initialize ConfigManager.

        Args:
            base_path: Base directory containing configuration files
        """
        self.base_path = base_path
        self._configs: Dict[str, Dict[str, Any]] = {}

    def load_config(
        self, config_name: str, override_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Load a YAML configuration file.

        Args:
            config_name: Name of the config file (without .yaml extension)
            override_path: Optional path to override config file

        Returns:
            Dictionary containing the parsed YAML configuration

        Raises:
            FileNotFoundError: If the config file doesn't exist
            yaml.YAMLError: If the YAML is invalid
        """
        # Use override path if provided, otherwise use base path
        if override_path:
            config_path = override_path
        else:
            config_path = self.base_path / f"{config_name}.yaml"

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Cache the config
        self._configs[config_name] = config

        return config

    def get_config(self, config_name: str) -> Dict[str, Any]:
        """Get a previously loaded configuration.

        Args:
            config_name: Name of the config file

        Returns:
            Dictionary containing the configuration

        Raises:
            KeyError: If the config hasn't been loaded yet
        """
        if config_name not in self._configs:
            raise KeyError(
                f"Configuration '{config_name}' not loaded. Call load_config() first."
            )
        return self._configs[config_name]

    def get_prompt_config(self, prompt_name: str) -> Dict[str, Any]:
        """Get a specific prompt configuration.

        Args:
            prompt_name: Name of the prompt (e.g., 'happiness_v2')

        Returns:
            Dictionary containing the prompt configuration

        Raises:
            KeyError: If prompts config not loaded or prompt not found
        """
        prompts_config = self.get_config("prompts")
        if prompt_name not in prompts_config.get("prompts", {}):
            raise KeyError(f"Prompt '{prompt_name}' not found in prompts configuration")
        return prompts_config["prompts"][prompt_name]

    def get_youtube_search(self, search_name: str) -> Dict[str, Any]:
        """Get a specific YouTube search configuration.

        Args:
            search_name: Name of the search config (e.g., 'music_search')

        Returns:
            Dictionary containing the search configuration

        Raises:
            KeyError: If youtube config not loaded or search not found
        """
        youtube_config = self.get_config("youtube")
        if search_name not in youtube_config.get("searches", {}):
            raise KeyError(f"Search '{search_name}' not found in youtube configuration")
        return youtube_config["searches"][search_name]

    def load_all_base_configs(self) -> None:
        """Load all base configuration files."""
        config_files = ["app", "prompts", "youtube"]
        for config_name in config_files:
            config_path = self.base_path / f"{config_name}.yaml"
            if config_path.exists():
                self.load_config(config_name)


def get_config_manager() -> ConfigManager:
    """Get a ConfigManager instance.

    Returns:
        ConfigManager instance with base path set to config/base
    """
    return ConfigManager()
