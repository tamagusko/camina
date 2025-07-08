import yaml
from pathlib import Path

def load_config(config_file: str = "main_config.yaml"):
    """Loads a YAML configuration file from the configs directory.

    Args:
        config_file: The name of the configuration file to load.

    Returns:
        A dictionary containing the configuration.
    """
    config_path = Path(__file__).parent.parent.parent.parent / "configs" / config_file
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def load_classes(classes_file: str = "classes.yaml"):
    """Loads the class mappings from a YAML file.

    Args:
        classes_file: The name of the classes file to load.

    Returns:
        A dictionary mapping class IDs to class names.
    """
    classes_path = Path(__file__).parent.parent.parent.parent / "configs" / classes_file
    with open(classes_path, "r") as f:
        return {int(k): v for k, v in yaml.safe_load(f).items()}
