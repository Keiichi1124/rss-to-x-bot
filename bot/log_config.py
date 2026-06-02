# bot/log_config.py
import logging
import sys
from pythonjsonlogger.json import JsonFormatter

def setup_logging(log_level=logging.INFO):
    """Configures logging to output CloudWatch-compatible JSON."""
    logger = logging.getLogger("bot") # Get root logger for the bot package
    logger.setLevel(log_level)
    logger.handlers.clear() # Remove existing handlers

    # Use jsonlogger
    # Format includes standard CloudWatch fields + Python logging fields
    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z"
    )

    # Log to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Optional: Configure logging for libraries if needed (e.g., requests)
    # logging.getLogger("requests").setLevel(logging.WARNING)
    # logging.getLogger("apscheduler").setLevel(logging.INFO)

# Example usage:
if __name__ == "__main__":
    setup_logging(log_level=logging.DEBUG)
    root_logger = logging.getLogger("bot")
    root_logger.debug("This is a debug message.")
    root_logger.info("This is an info message.")
    root_logger.warning("This is a warning message.")
    root_logger.error("This is an error message.")

    sub_logger = logging.getLogger("bot.submodule")
    sub_logger.info("Message from submodule.")
