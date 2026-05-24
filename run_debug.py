import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "debug.log"), mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ]
)

from whisprnick.app import Application
app = Application()
app.run()
