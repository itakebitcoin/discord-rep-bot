import json
import os

def load_config():
    with open('config.json', 'r') as file:
        return json.load(file)

def ensure_ratings_file_exists(ratings_file):
    if not os.path.exists(ratings_file):
        with open(ratings_file, 'w') as file:
            json.dump({}, file)

def get_user_reputation(user_id, ratings_file):
    with open(ratings_file, 'r') as file:
        ratings_data = json.load(file)
    
    user_data = ratings_data.get(str(user_id), {"rep": 0, "reviews": []})
    user_ratings = user_data.get("reviews", [])
    
    if isinstance(user_ratings, list):
        total_rep = sum(1 if rating['good_transaction'] else -1 for rating in user_ratings)
    else:
        total_rep = 0  # Default to 0 if user_ratings is not a list
        user_ratings = []
    
    return total_rep, user_ratings