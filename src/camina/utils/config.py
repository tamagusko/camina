import yaml
from pathlib import Path
from typing import Dict, Any


def _get_project_root() -> Path:
    """Get the project root directory."""
    current_path = Path(__file__).resolve()
    # Go up until we find the configs directory
    for parent in current_path.parents:
        if (parent / "configs").exists():
            return parent
    # Fallback to the old method
    return Path(__file__).parent.parent.parent.parent


def load_config(config_file: str = "main_config.yaml") -> Dict[str, Any]:
    """Loads a YAML configuration file from the configs directory.

    Args:
        config_file: The name of the configuration file to load.

    Returns:
        A dictionary containing the configuration.
    """
    config_path = _get_project_root() / "configs" / config_file
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def load_classes(classes_file: str = "classes.yaml") -> Dict[int, str]:
    """Loads the class mappings from a YAML file.

    Args:
        classes_file: The name of the classes file to load.

    Returns:
        A dictionary mapping class IDs to class names.
    """
    classes_path = _get_project_root() / "configs" / classes_file
    with open(classes_path, "r") as f:
        return {int(k): v for k, v in yaml.safe_load(f).items()}
