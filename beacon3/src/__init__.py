try:
    # If imported as a subpackage (beacon3.src)
    from ..logging_config import setup_logging  # type: ignore
except Exception:
    try:
        # If imported as top-level package (src)
        from logging_config import setup_logging  # type: ignore
    except Exception:
        setup_logging = None  # type: ignore

# Initialize logging at import time for the service context
try:
    if setup_logging:
        setup_logging()
except Exception:
    pass

