"""
Check Library YAML Loader.

Loads, parses, and validates check library YAML files into immutable CheckLibrary models.
"""

from pathlib import Path
from typing import Any, Dict, Union
import yaml
from pydantic import ValidationError

from app.checks.exceptions import CheckValidationError, OverlappingVersionError
from app.checks.models import CheckLibrary


def load_check_library_from_dict(data: Dict[str, Any]) -> CheckLibrary:
    """
    Construct and validate a CheckLibrary from a raw dictionary.
    
    Args:
        data: Dictionary loaded from YAML or JSON.
        
    Returns:
        Validated CheckLibrary instance.
        
    Raises:
        CheckValidationError: If schema or validation invariants fail.
        OverlappingVersionError: If overlapping date ranges exist for the same check.
    """
    if not isinstance(data, dict):
        raise CheckValidationError(f"Expected dictionary for check library root, got {type(data).__name__}")

    try:
        return CheckLibrary.model_validate(data)
    except OverlappingVersionError:
        raise
    except (ValidationError, ValueError) as e:
        raise CheckValidationError(f"Check library validation failed: {e}") from e


def load_check_library_from_yaml(file_path: Union[str, Path]) -> CheckLibrary:
    """
    Load and validate a CheckLibrary from a YAML file.
    
    Args:
        file_path: Path to YAML file.
        
    Returns:
        Validated CheckLibrary instance.
        
    Raises:
        CheckValidationError: If file is missing, cannot be parsed, or fails validation.
    """
    path = Path(file_path)
    if not path.exists():
        raise CheckValidationError(f"Check library file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_content = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise CheckValidationError(f"Failed to parse YAML from {path}: {e}") from e

    if raw_content is None:
        raw_content = {"checks": []}

    return load_check_library_from_dict(raw_content)
