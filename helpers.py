import csv
import datetime
import urllib
import uuid
from flask import render_template

def apology(message, code=400):
    """Render message as an apology to user."""