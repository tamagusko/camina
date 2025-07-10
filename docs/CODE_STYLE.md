# Code Style Guide

## Python Code Style

This project follows PEP 8 conventions with the following specifics:

### Type Hints
- All function parameters and return types should include type hints
- Use `typing` module for complex types
- Example:
```python
from typing import Dict, List, Optional, Union

def process_data(data: List[Dict[str, Union[str, int]]], threshold: float = 0.5) -> Optional[Dict[str, int]]:
    # implementation
    pass
```

### Import Organization
Follow this order:
1. Standard library imports
2. Third-party imports (numpy, cv2, etc.)
3. Local application imports

### Docstrings
- Use Google-style docstrings
- Include Args, Returns, and Raises sections as needed
- Example:
```python
def load_config(config_file: str = "main_config.yaml") -> Dict[str, Any]:
    """Loads a YAML configuration file from the configs directory.

    Args:
        config_file: The name of the configuration file to load.

    Returns:
        A dictionary containing the configuration.
    """
```

### Line Length
- Maximum 88 characters per line
- Use parentheses for line continuation in function calls

### Naming Conventions
- Classes: PascalCase (`ModalShareCounterApp`)
- Functions/methods: snake_case (`load_config`)
- Variables: snake_case (`frame_count`)
- Constants: UPPER_CASE (`CONFIG`)

### Error Handling
- Use specific exception types
- Include meaningful error messages
- Handle optional dependencies gracefully

### Configuration
- Use snake_case for all configuration keys
- Group related settings with comments
- Provide sensible defaults