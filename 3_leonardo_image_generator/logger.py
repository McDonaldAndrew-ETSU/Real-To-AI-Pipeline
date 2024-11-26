import logging


class ColorLogger(logging.Logger):
    """Custom logger class with colorized output using ANSI escape codes."""

    def __init__(self, name):
        super().__init__(name)
        self.setLevel(logging.DEBUG)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)

        log_format = "%(asctime)s - %(name)s - %(funcName)s - Line: %(lineno)d - %(levelname)s: %(message)s"
        formatter = self.ColorFormatter(log_format)

        console_handler.setFormatter(formatter)
        self.addHandler(console_handler)

    class ColorFormatter(logging.Formatter):
        """Custom formatter to add colorized log messages using ANSI escape codes."""

        RESET = "\033[0m"
        BOLD = "\033[1m"
        COLORS = {
            "DEBUG": "\033[94m",  # Blue
            "INFO": "\033[92m",  # Green
            "WARNING": "\033[93m",  # Yellow
            "ERROR": "\033[91m",  # Red
            "CRITICAL": "\033[95m",  # Magenta
        }

        def format(self, record):
            """Formats the log record with color and styles based on the log level."""
            bold = self.BOLD
            color = self.COLORS.get(record.levelname, self.RESET)

            if record.levelname == "CRITICAL":
                levelname = f"{bold}{color}{record.levelname}{self.RESET}"
                record.levelname = levelname

            message = f"{color}{record.getMessage()}{self.RESET}"
            record.msg = message

            return super().format(record)


# Example usage:
if __name__ == "__main__":
    logger = ColorLogger(__name__)
    logger.debug("This is a debug message.")
    logger.info("This is an info message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")
    logger.critical("This is a critical message.")
