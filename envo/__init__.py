# flake8: noqa E402, F401

import warnings
import sys
# sys.stderr = lambda x: None

warnings.warn = lambda *args, **kwargs: None
warnings._showwarnmsg = lambda x: None

# warnings.simplefilter("ignore")

from rich.traceback import install
from rich.console import Console

install()

console = Console()
console._force_terminal = True

from envo import e2e
from envo.logging import logger
from envo.devops import *
from envo.env import *
from envo.plugins import *
from envo.misc import EnvoError
from envo import dependency_watcher

dependency_watcher.enable()
