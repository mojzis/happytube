# Phase 1: Core Infrastructure

**Timeline:** Day 1-2

## Overview

This phase establishes the foundational components that all other phases will build upon. We'll create the directory structure, implement core utilities, and set up configuration management.

## Goals

- Set up modular, maintainable directory structure
- Implement reusable markdown file handling
- Configure environment-based settings with validation
- Create YAML-based configuration system
- Establish logging infrastructure
- Define base classes for stage-based architecture

## Tasks

### 1. Directory Structure Setup

Create the following directory structure:

```
happytube/
├── config/
│   ├── base/
│   │   ├── app.yaml
│   │   ├── prompts.yaml
│   │   └── youtube.yaml
│   └── experiments/
├── stages/
│   ├── fetch/
│   ├── assess/
│   ├── enhance/
│   └── report/
├── parquet/
│   ├── fetch/
│   ├── assess/
│   └── enhance/
├── templates/
│   ├── base.html
│   └── daily_report.html
├── happytube/
│   ├── cli/
│   ├── stages/
│   ├── config/
│   ├── models/
│   └── utils/
└── scripts/
```

**Commands:**
```bash
mkdir -p config/base config/experiments
mkdir -p stages/{fetch,assess,enhance,report}
mkdir -p parquet/{fetch,assess,enhance}
mkdir -p templates
mkdir -p happytube/{cli,stages,config,models,utils}
mkdir -p scripts
```

### 2. Implement MarkdownFile Class

**File:** `happytube/models/markdown.py`

**Purpose:** Handle markdown files with YAML frontmatter for storing video data.

**Key Features:**
- Parse YAML frontmatter from markdown files
- Save markdown files with frontmatter
- Update frontmatter fields
- Convert to/from string format

**Implementation:**
```python
import yaml
from pathlib import Path
from typing import Dict, Any

class MarkdownFile:
    """Represents a Markdown file with YAML frontmatter."""

    def __init__(self, frontmatter: Dict[str, Any], content: str):
        self.frontmatter = frontmatter
        self.content = content

    @classmethod
    def load(cls, file_path: Path) -> "MarkdownFile":
        """Load a Markdown file with frontmatter."""
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()

        # Split frontmatter and content
        if text.startswith('---\n'):
            parts = text.split('---\n', 2)
            frontmatter = yaml.safe_load(parts[1])
            content = parts[2].strip()
        else:
            frontmatter = {}
            content = text

        return cls(frontmatter, content)

    def save(self, file_path: Path) -> None:
        """Save the Markdown file with frontmatter."""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.to_string())

    def to_string(self) -> str:
        """Convert to string format with frontmatter."""
        yaml_str = yaml.dump(self.frontmatter, default_flow_style=False, sort_keys=False)
        return f"---\n{yaml_str}---\n\n{self.content}"

    def update_frontmatter(self, updates: Dict[str, Any]) -> None:
        """Update frontmatter with new values."""
        self.frontmatter.update(updates)
```

**Dependencies to add:**
```bash
poetry add pyyaml
```

### 3. Implement Pydantic Settings

**File:** `happytube/config/settings.py`

**Purpose:** Load and validate application settings from environment variables.

**Key Features:**
- Load from `.env` file
- Validate API keys presence
- Provide type-safe access to configuration
- Validate log levels

**Implementation:**
```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API Keys
    youtube_api_key: str = Field(..., alias="YTKEY", description="YouTube Data API key")
    anthropic_api_key: str = Field(..., description="Anthropic Claude API key")

    # Application
    log_level: str = Field(default="INFO", description="Logging level")
    environment: str = Field(default="development", description="Environment name")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper

    @property
    def has_all_credentials(self) -> bool:
        """Check if all required credentials are configured."""
        return bool(self.youtube_api_key and self.anthropic_api_key)

def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
```

**Dependencies to add:**
```bash
poetry add pydantic-settings
```

### 4. Create ConfigManager for YAML Config Loading

**File:** `happytube/config/config_manager.py`

**Purpose:** Load and manage YAML configuration files.

**Key Features:**
- Load base configuration files
- Support for experiment overrides
- Merge configurations
- Validate configuration structure

**Implementation:**
```python
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

class ConfigManager:
    """Manages loading and accessing YAML configuration files."""

    def __init__(self, config_dir: Path = Path("config")):
        self.config_dir = config_dir
        self.base_dir = config_dir / "base"
        self.experiments_dir = config_dir / "experiments"
        self._configs: Dict[str, Any] = {}

    def load_base_config(self, config_name: str) -> Dict[str, Any]:
        """Load a base configuration file."""
        config_path = self.base_dir / f"{config_name}.yaml"

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        self._configs[config_name] = config
        return config

    def load_experiment_config(self, experiment_name: str) -> Dict[str, Any]:
        """Load an experiment configuration file."""
        config_path = self.experiments_dir / f"{experiment_name}.yaml"

        if not config_path.exists():
            raise FileNotFoundError(f"Experiment config not found: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def get_config(self, config_name: str) -> Dict[str, Any]:
        """Get a loaded configuration by name."""
        if config_name not in self._configs:
            self.load_base_config(config_name)
        return self._configs[config_name]

    def merge_configs(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Merge two configuration dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if isinstance(value, dict) and key in result and isinstance(result[key], dict):
                result[key] = self.merge_configs(result[key], value)
            else:
                result[key] = value
        return result
```

### 5. Implement Base Stage Class

**File:** `happytube/stages/base.py`

**Purpose:** Define abstract base class for all processing stages.

**Key Features:**
- Common stage directory management
- Abstract run method for implementation by subclasses
- Date-based organization
- Consistent interface for all stages

**Implementation:**
```python
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import date
from typing import Dict, Any

class Stage(ABC):
    """Base class for all processing stages."""

    def __init__(self, stage_name: str, base_path: Path = Path("stages")):
        self.stage_name = stage_name
        self.stage_path = base_path / stage_name

    def get_stage_dir(self, target_date: date) -> Path:
        """Get stage directory for date."""
        return self.stage_path / target_date.strftime("%Y-%m-%d")

    def ensure_stage_dir(self, target_date: date) -> Path:
        """Create stage directory if needed."""
        stage_dir = self.get_stage_dir(target_date)
        stage_dir.mkdir(parents=True, exist_ok=True)
        return stage_dir

    @abstractmethod
    async def run(self, target_date: date) -> Dict[str, Any]:
        """Run the stage. Returns stats dict."""
        pass
```

### 6. Set Up Centralized Logging

**File:** `happytube/utils/logging.py`

**Purpose:** Provide consistent logging across the application.

**Key Features:**
- Configurable log levels
- Rich console output
- File logging support
- Structured logging

**Implementation:**
```python
import logging
import sys
from pathlib import Path
from rich.logging import RichHandler
from rich.console import Console

console = Console()

def setup_logging(log_level: str = "INFO", log_file: Path | None = None) -> logging.Logger:
    """Set up application logging with Rich handler."""

    # Create logger
    logger = logging.getLogger("happytube")
    logger.setLevel(log_level)

    # Remove existing handlers
    logger.handlers.clear()

    # Rich console handler
    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        markup=True,
    )
    rich_handler.setLevel(log_level)

    # Format
    formatter = logging.Formatter(
        "%(message)s",
        datefmt="[%X]",
    )
    rich_handler.setFormatter(formatter)
    logger.addHandler(rich_handler)

    # File handler (optional)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger

def get_logger() -> logging.Logger:
    """Get the application logger."""
    return logging.getLogger("happytube")
```

**Dependencies to add:**
```bash
poetry add rich
```

### 7. Create Base Configuration Files

**File:** `config/base/app.yaml`

```yaml
version: "1.0"
metadata:
  name: "happytube"
  description: "YouTube happiness analyzer"

paths:
  stages_base: "stages"
  templates: "templates"
  parquet_export: "parquet"

processing:
  happiness_threshold: 3
  max_videos_per_run: 50
  default_youtube_config: "music_search"
  default_prompt_config: "happiness_v2"

export:
  parquet_days_back: 7
  report_format: "html"
```

**File:** `config/base/prompts.yaml`

```yaml
version: "1.0"
prompts:
  happiness_v2:
    name: "Happiness Assessment CSV v2"
    version: "2.0"
    model: "claude-3-opus-20240229"
    max_tokens: 4096
    template: |
      {csv_content}

      Rate the happiness level (1-5 scale) of each video based on:
      - Title sentiment
      - Description content
      - Category context

      Return CSV with columns: video_id,happiness,reasoning
      Keep reasoning concise (max 100 chars).

  enhance_description_v1:
    name: "Description Enhancement v1"
    version: "1.0"
    model: "claude-3-opus-20240229"
    max_tokens: 2048
    template: |
      Improve this video description by removing:
      - Clickbait language
      - "Like and subscribe" spam
      - Excessive links
      - Overly promotional content

      Title: {title}
      Description: {description}

      Return only the enhanced description. Keep it natural and informative.
```

**File:** `config/base/youtube.yaml`

```yaml
version: "1.0"
searches:
  music_search:
    name: "Music Videos"
    params:
      regionCode: "CZ"
      videoDuration: "medium"
      videoCategoryId: 15  # Music
      order: "viewCount"
      safeSearch: "strict"
      maxResults: 50

  educational_search:
    name: "Educational Content"
    params:
      regionCode: "US"
      videoDuration: "medium"
      videoCategoryId: 27  # Education
      order: "relevance"
      safeSearch: "strict"
      maxResults: 30

  entertainment_search:
    name: "Entertainment Videos"
    params:
      regionCode: "CZ"
      videoDuration: "medium"
      videoCategoryId: 24  # Entertainment
      order: "viewCount"
      safeSearch: "strict"
      maxResults: 50
```

## Testing Phase 1

After completing this phase, verify everything works:

```bash
# Test settings loading
poetry run python -c "from happytube.config.settings import get_settings; s = get_settings(); print(f'Settings loaded: {s.has_all_credentials}')"

# Test config manager
poetry run python -c "from happytube.config.config_manager import ConfigManager; cm = ConfigManager(); print(cm.load_base_config('app'))"

# Test markdown file
poetry run python -c "from happytube.models.markdown import MarkdownFile; from pathlib import Path; mf = MarkdownFile({'test': 'value'}, 'content'); mf.save(Path('test.md')); loaded = MarkdownFile.load(Path('test.md')); print(loaded.frontmatter)"

# Test logging
poetry run python -c "from happytube.utils.logging import setup_logging; logger = setup_logging('INFO'); logger.info('Test message')"
```

## Dependencies Summary

Add these dependencies in this phase:

```bash
poetry add pyyaml
poetry add pydantic-settings
poetry add rich
```

## Success Criteria

- ✅ All directories created
- ✅ MarkdownFile class can load/save files with frontmatter
- ✅ Settings class loads from .env and validates
- ✅ ConfigManager loads YAML files
- ✅ Base Stage class defined
- ✅ Logging works with Rich console output
- ✅ All base configuration files created
- ✅ All tests pass

## Next Phase

Phase 2 will implement the concrete stage classes (Fetch, Assess, Enhance, Report) using the infrastructure built in this phase.
