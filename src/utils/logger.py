import logging
import os
import sys

def setup_logging(log_dir="log", log_file="app.log", level=logging.DEBUG):
    """
    Configures the logging for the application.
    Creates the log directory if it doesn't exist.
    """
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except OSError as e:
            print(f"Error creating log directory: {e}", file=sys.stderr)
            return

    log_path = os.path.join(log_dir, log_file)

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_path, mode='w'),
            logging.StreamHandler(sys.stdout)
        ]
    )

    logging.info(f"Logging initialized. Log file: {log_path}")

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logging.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception
