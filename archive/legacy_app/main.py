"""
Main entry point for the Camina application.
"""

from typing import Dict, Union

from src.camina.app import ModalShareCounterApp
from src.camina.utils.config import load_config


def main() -> None:
    """Loads configuration and runs the application."""
    config: Dict[str, Union[str, int, float, bool]] = load_config()
    app = ModalShareCounterApp(config)
    app.run()


if __name__ == "__main__":
    main()
