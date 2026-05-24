import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from whisprnick.app import Application

app = Application()
app.run()
