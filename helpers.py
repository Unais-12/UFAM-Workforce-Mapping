import csv
import datetime
import urllib
import uuid
from flask import render_template

def apology(message, code=400):
    """Render message as an apology to user."""

    
def determine_next_category(current_category, current_question_index, questions_per_category):
    categories = list(questions_per_category.keys())
    current_index = categories.index(current_category)
    
    # If there's a next category, return it
    if current_index < len(categories) - 1:
        next_category = categories[current_index + 1]
        return next_category, 0  # Start with the first question of the next category
    
    # No more categories
    return None, None
