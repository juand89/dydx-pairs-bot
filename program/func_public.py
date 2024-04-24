from constants import RESOLUTION
from func_utils import get_iso_times
from pprint import pprint
import pandas as pd
import numpy as np
import time


ISO_TIMES = get_iso_times()

pprint(ISO_TIMES)

# construct makert prices
def construct_market_prices(client):
    pass