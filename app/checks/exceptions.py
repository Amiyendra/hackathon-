"""Check library exception definitions."""


class CheckLibraryError(Exception):
    """Base exception for check library errors."""
    pass


class CheckValidationError(CheckLibraryError):
    """Raised when check definition or library validation fails."""
    pass


class VersionResolutionError(CheckLibraryError):
    """Base exception for check version resolution errors."""
    pass


class NoMatchingVersionError(VersionResolutionError):
    """Raised when no active check version is valid for the specified call date."""
    pass


class OverlappingVersionError(VersionResolutionError):
    """Raised when multiple active versions match the same call date or date windows overlap."""
    pass
