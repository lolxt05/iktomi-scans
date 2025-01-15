import os
import logging

# Get the script's filename
python_name = os.path.basename(__file__)

# Clear existing handlers from the root logger
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Set up a custom formatter
formatter = logging.Formatter(f'{python_name}:%(levelname)s:%(message)s')

# Create and configure the FileHandler
file_handler = logging.FileHandler('test.log', encoding='utf-8')
file_handler.setFormatter(formatter)

# Add the handler to the root logger
logging.basicConfig(level=logging.DEBUG, handlers=[file_handler])

# Example log
logging.debug("This is a debug message.")
