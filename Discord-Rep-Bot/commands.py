import discord
from discord import app_commands
import json
from utils import ensure_ratings_file_exists

async def ratings(interaction: discord.Interaction, user: discord.Member, ratings_file):
    # Load the ratings from the file
    ensure_ratings_file_exists(ratings_file)
    with open(ratings_file, 'r') as file:
        ratings = json.load(file)

    user_ratings = ratings.get(str(user.id), {"rep": 0, "reviews": []})

    response_message = f"{user.mention} has {user_ratings['rep']} rep."

    await interaction.response.send_message(response_message, ephemeral=True)