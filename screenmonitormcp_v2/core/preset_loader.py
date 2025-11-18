"""Gaming preset loader for ScreenMonitorMCP v2."""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import structlog

from .gaming_mode import PerformanceMode, GameStreamConfig

logger = structlog.get_logger(__name__)


class PresetLoader:
    """Load and manage gaming presets from configuration file."""

    def __init__(self, preset_file: Optional[str] = None):
        """Initialize preset loader.

        Args:
            preset_file: Path to preset JSON file (default: gaming_presets.json)
        """
        if preset_file is None:
            # Default to gaming_presets.json in project root
            project_root = Path(__file__).parent.parent.parent
            preset_file = project_root / "gaming_presets.json"

        self.preset_file = Path(preset_file)
        self.presets = {}
        self.game_specific_presets = {}
        self.load_presets()

    def load_presets(self) -> None:
        """Load presets from JSON file."""
        try:
            if not self.preset_file.exists():
                logger.warning(f"Preset file not found: {self.preset_file}")
                return

            with open(self.preset_file, 'r') as f:
                data = json.load(f)

            self.presets = data.get("presets", {})
            self.game_specific_presets = data.get("game_specific_presets", {})

            logger.info(f"Loaded {len(self.presets)} presets and "
                       f"{len(self.game_specific_presets)} game-specific presets")

        except Exception as e:
            logger.error(f"Failed to load presets: {e}")

    def get_preset(self, preset_name: str) -> Optional[Dict[str, Any]]:
        """Get a preset by name.

        Args:
            preset_name: Name of the preset

        Returns:
            Preset configuration dict or None
        """
        # Check standard presets
        if preset_name in self.presets:
            return self.presets[preset_name]

        # Check game-specific presets
        if preset_name in self.game_specific_presets:
            game_preset = self.game_specific_presets[preset_name]
            parent_name = game_preset.get("parent")

            if parent_name and parent_name in self.presets:
                # Merge parent preset with overrides
                preset = self.presets[parent_name].copy()
                overrides = game_preset.get("overrides", {})

                # Merge config overrides
                if "config" in preset:
                    preset["config"].update(overrides)

                # Add game-specific metadata
                preset["name"] = game_preset.get("name", preset_name)
                preset["notes"] = game_preset.get("notes", "")

                return preset

        logger.warning(f"Preset not found: {preset_name}")
        return None

    def get_config_from_preset(
        self,
        preset_name: str,
        **overrides
    ) -> Optional[GameStreamConfig]:
        """Get GameStreamConfig from preset name.

        Args:
            preset_name: Name of the preset
            **overrides: Override specific config values

        Returns:
            GameStreamConfig or None
        """
        preset = self.get_preset(preset_name)
        if not preset:
            return None

        config_data = preset.get("config", {})

        # Apply overrides
        config_data.update(overrides)

        # Map mode string to PerformanceMode
        mode_str = preset.get("mode", "balanced")
        try:
            mode = PerformanceMode(mode_str)
        except ValueError:
            logger.warning(f"Invalid mode '{mode_str}', using balanced")
            mode = PerformanceMode.BALANCED

        # Create config
        config = GameStreamConfig(mode=mode)

        # Apply settings
        if "fps" in config_data:
            config.fps = config_data["fps"]
        if "quality" in config_data:
            config.quality = config_data["quality"]
        if "format" in config_data:
            config.format = config_data["format"]
        if "enable_frame_skip" in config_data:
            config.enable_frame_skip = config_data["enable_frame_skip"]
        if "adaptive_quality" in config_data:
            config.adaptive_quality = config_data["adaptive_quality"]
        if "cache_size" in config_data:
            config.cache_size = config_data["cache_size"]

        return config

    def list_presets(self) -> Dict[str, str]:
        """List all available presets.

        Returns:
            Dict mapping preset names to descriptions
        """
        result = {}

        # Add standard presets
        for name, preset in self.presets.items():
            result[name] = preset.get("description", "")

        # Add game-specific presets
        for name, preset in self.game_specific_presets.items():
            result[name] = preset.get("name", name)

        return result

    def get_preset_info(self, preset_name: str) -> Optional[str]:
        """Get detailed information about a preset.

        Args:
            preset_name: Name of the preset

        Returns:
            Formatted preset information string
        """
        preset = self.get_preset(preset_name)
        if not preset:
            return None

        config = preset.get("config", {})
        lines = [
            f"Preset: {preset.get('name', preset_name)}",
            f"Description: {preset.get('description', 'N/A')}",
            "",
            "Configuration:",
            f"  FPS: {config.get('fps', 'N/A')}",
            f"  Quality: {config.get('quality', 'N/A')}%",
            f"  Format: {config.get('format', 'N/A').upper()}",
            f"  Frame Skip: {config.get('enable_frame_skip', False)}",
            f"  Adaptive Quality: {config.get('adaptive_quality', False)}",
            f"  Cache Size: {config.get('cache_size', 'N/A')} frames",
            "",
            f"Expected Latency: {preset.get('expected_latency_ms', 'N/A')}ms",
            f"Recommended For: {preset.get('recommended_for', 'N/A')}",
        ]

        if "use_cases" in preset:
            lines.append("")
            lines.append("Use Cases:")
            for use_case in preset["use_cases"]:
                lines.append(f"  - {use_case}")

        if "notes" in preset and preset["notes"]:
            lines.append("")
            lines.append(f"Notes: {preset['notes']}")

        return "\n".join(lines)


# Global instance
preset_loader = PresetLoader()
