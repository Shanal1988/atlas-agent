import logging

def configure_logging(level: str = "WARNING", log_to_file: bool = False) -> None:
    """Configure the root logger for Atlas Agent.

    Args:
        level: Logging level name (e.g., "DEBUG", "INFO", "WARNING", "ERROR").
        log_to_file: If True, also log to a rotating file under ./logs/atlas_agent.log.
    """
    numeric_level = getattr(logging, level.upper(), logging.WARNING)
    handlers = [logging.StreamHandler()]
    if log_to_file:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler("logs/atlas_agent.log", maxBytes=5_000_000, backupCount=3)
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        handlers.append(file_handler)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )
}
