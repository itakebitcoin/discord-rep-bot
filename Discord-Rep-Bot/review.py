print("Script started")

import json
import discord
from discord.ext import commands
import sqlite3
import re
from utils import load_config, ensure_ratings_file_exists
from forum_checker import handle_thread_create, handle_thread_message, NotifiedThreads
from rep_roles import update_rep_role  # <-- Import the role updater
import asyncio
import io
import sys
from contextlib import redirect_stdout, redirect_stderr
import logging
import builtins
import random

print("Imported core modules.")

# --- Load Cities ---
def load_cities(filename="cities.txt"):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            print(f"Loaded {filename}.")
            return [
                line.strip() for line in f
                if line.strip() and not line.strip().startswith("#")
            ]
    except FileNotFoundError:
        print(f"Warning: {filename} not found.")
        return []

CITIES = load_cities()
print("Cities loaded.")

# --- Config and Bot Setup ---

config = load_config()
print("Config loaded.")

TARGET_CHANNEL_ID = int(config['target_channel_id'])
FORUM_CHANNEL_ID = int(config.get('forum_channel_id', 0))
MISSING_PRICE_TAG_NAME = config.get('missing_price_tag_name', 'Missing Price')
MISSING_LOCATION_TAG_NAME = config.get('missing_location_tag_name', 'Missing Location')
LOG_CHANNEL_ID = int(config.get('log_channel_id', 0))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)
print("Bot object created.")

notified_threads = NotifiedThreads()  # Use the class, not a dict

async def send_log(message):
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        await channel.send(message)
        print(f"Sent log message to channel {LOG_CHANNEL_ID}.")
    else:
        print(f"Failed to send log message: channel {LOG_CHANNEL_ID} not found.")

# --- Example rep storage and retrieval ---
def get_rep(user_id):
    # Dummy implementation, replace with your actual DB logic
    try:
        with sqlite3.connect("reviews.db") as conn:
            c = conn.cursor()
            c.execute('SELECT rep_total FROM rep_totals WHERE user_id = ?', (user_id,))
            row = c.fetchone()
            return row[0] if row else 0
    except Exception as e:
        print(f"Error fetching rep for {user_id}: {e}")
        return 0

def add_rep(user_id, amount):
    try:
        with sqlite3.connect("reviews.db") as conn:
            c = conn.cursor()
            c.execute('CREATE TABLE IF NOT EXISTS rep_totals (user_id INTEGER PRIMARY KEY, rep_total INTEGER)')
            c.execute('SELECT rep_total FROM rep_totals WHERE user_id = ?', (user_id,))
            row = c.fetchone()
            new_total = (row[0] if row else 0) + amount
            c.execute('INSERT OR REPLACE INTO rep_totals (user_id, rep_total) VALUES (?, ?)', (user_id, new_total))
            conn.commit()
    except Exception as e:
        print(f"Error adding rep for {user_id}: {e}")

# --- Event Handlers using forum_checker ---
forum_checker_enabled = True

@bot.tree.command(name="forumchecker", description="Enable or disable the forum checker (admin only)")
async def forumchecker_command(interaction: discord.Interaction, state: str):
    admin_role_id = 1159251626389930045
    if not any(role.id == admin_role_id for role in getattr(interaction.user, "roles", [])):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    global forum_checker_enabled
    if state.lower() == "enable":
        forum_checker_enabled = True
        await interaction.response.send_message("Forum checker enabled.")
    elif state.lower() == "disable":
        forum_checker_enabled = False
        await interaction.response.send_message("Forum checker disabled.")
    else:
        await interaction.response.send_message("Usage: /forumchecker <enable|disable>", ephemeral=True)

@bot.event
async def on_thread_create(thread):
    print(f"on_thread_create event triggered for thread ID {thread.id}.")
    if forum_checker_enabled:
        await handle_thread_create(
            thread,
            FORUM_CHANNEL_ID,
            MISSING_PRICE_TAG_NAME,
            MISSING_LOCATION_TAG_NAME,
            CITIES
        )
        print("Forum checker handled thread creation.")
    else:
        print("Forum checker is disabled.")

@bot.event
async def on_message(message):
    # --- Ignore threads cleared by !clear ---
    if (
        isinstance(message.channel, discord.Thread)
        and hasattr(bot, "ignored_threads")
        and message.channel.id in bot.ignored_threads
    ):
        await bot.process_commands(message)
        return

    # Sticky message logic for the rep channel
    if message.channel.id == STICKY_CHANNEL_ID and not message.author.bot:
        await send_sticky_message(message.channel)

    # Only run forum checker if enabled
    if forum_checker_enabled:
        await handle_thread_message(
            message,
            FORUM_CHANNEL_ID,
            MISSING_PRICE_TAG_NAME,
            MISSING_LOCATION_TAG_NAME,
            CITIES,
            notified_threads
        )
    await bot.process_commands(message)

    # --- Admin clear tags and ignore thread logic ---
    if (
        isinstance(message.channel, discord.Thread)
        and message.content.strip().lower() == "!clear"
        and message.author.guild_permissions.administrator
    ):
        tags = message.channel.parent.available_tags
        missing_price_tag = discord.utils.get(tags, name=MISSING_PRICE_TAG_NAME)
        missing_location_tag = discord.utils.get(tags, name=MISSING_LOCATION_TAG_NAME)
        current_tags = list(message.channel.applied_tags)
        updated_tags = [tag for tag in current_tags if tag not in [missing_price_tag, missing_location_tag]]
        if set(updated_tags) != set(current_tags):
            await message.channel.edit(applied_tags=updated_tags)
            await message.channel.send(f"{message.author.mention} cleared missing info tags as admin.")

        # Delete previous bot messages in the thread
        async for msg in message.channel.history(limit=100):
            if msg.author == bot.user or msg.id == message.id:
                try:
                    await msg.delete()
                except Exception as e:
                    print(f"Failed to delete bot message: {e}")

        # Also delete the admin's !clear message
        try:
            await message.delete()
        except Exception as e:
            print(f"Failed to delete admin's !clear message: {e}")

        # Ignore this thread for future notifications
        notified_threads.pop(message.channel.id)
        # Add thread to ignore list
        if not hasattr(bot, "ignored_threads"):
            bot.ignored_threads = set()
        bot.ignored_threads.add(message.channel.id)

    # Rep by mention logic
    if (
        message.channel.id == TARGET_CHANNEL_ID
        and not message.author.bot
        and bot.user in message.mentions
        and len(message.mentions) > 1
    ):
        target_user = next((u for u in message.mentions if u != bot.user and u != message.author), None)
        if not target_user:
            return
        if target_user.id == message.author.id:
            await message.channel.send(
                f"{message.author.mention}, you cannot rate yourself.",
                reference=message
            )
            return
        content = message.content.lower()
        rep_change = 0
        if any(word in content for word in ["10/10", "9/10", "8/10", "7/10", "6/10", "good", "great", "awesome", "legit", "smooth", "positive", "+1"]):
            rep_change = 1
        elif any(word in content for word in ["0/10", "1/10", "2/10", "3/10", "4/10", "5/10", "scam", "scammer", "bad", "negative", "problem", "-1"]):
            rep_change = -1
        else:
            await message.channel.send(
                f"{message.author.mention}, please include a clear rating (e.g., 10/10 or scammer).",
                reference=message
            )
            return
        add_rep(target_user.id, rep_change)
        rep = get_rep(target_user.id)
        if rep_change > 0:
            await message.channel.send(
                f"{target_user.mention} received **+1 rep** from {message.author.mention}. Total: **{rep}**",
                reference=message
            )
        else:
            await message.channel.send(
                f"{target_user.mention} received **-1 rep** from {message.author.mention}. Total: **{rep}**",
                reference=message
            )
        await update_rep_role(target_user)  # Update the rep role

    # Rep correction logic
    if (
        message.channel.id == TARGET_CHANNEL_ID
        and not message.author.bot
        and len(message.mentions) >= 1
        and bot.user not in message.mentions
    ):
        # Check for rep keywords in the message
        lowered = message.content.lower()
        rep_keywords = ["10/10", "9/10", "8/10", "7/10", "6/10", "good", "great", "awesome", "legit", "smooth", "positive", "+1", "1/10", "2/10", "3/10", "4/10", "5/10", "scam", "scammer", "bad", "negative", "problem", "-1"]
        correction_messages = [
            "Hey numbnuts, you forgot to mention me first to count rep.",
            "Oi {mention}, you gotta tag me AND the user for rep to work genius!",
            "Rep doesn't count unless you mention me, {mention}. Try again!",
            "Pro tip: Mention the bot and the user, {mention}, or your rep won't count!",
            "Hey everyone look!{mention} doesnt know how to do this properly."
        ]
        if any(word in lowered for word in rep_keywords):
            reply = random.choice(correction_messages).replace("{mention}", message.author.mention)
            await message.channel.send(reply, reference=message)

def _call_update_rep_role_silent(member, rep=None):
    """
    Call update_rep_role while suppressing stdout/stderr, print(), and most logging
    so it doesn't log every user update. Returns the coroutine (caller should await).
    """
    f = io.StringIO()
    real_print = builtins.print
    prev_logging_disable = logging.root.manager.disable
    try:
        # silence print()
        builtins.print = lambda *a, **k: None
        # raise logging threshold to CRITICAL so normal logs are suppressed
        logging.disable(logging.CRITICAL)
        with redirect_stdout(f), redirect_stderr(f):
            if rep is None:
                coro = update_rep_role(member)
            else:
                coro = update_rep_role(member, rep)
            return coro
    finally:
        # restore print and logging threshold
        builtins.print = real_print
        logging.disable(prev_logging_disable)
        # drop buffered output
        _ = f.getvalue()

async def refresh_rep_nicknames():
    """
    Refreshes all members' nicknames to include their rep every hour.
    Logs completion to the command prompt only.
    """
    while True:
        for guild in bot.guilds:
            for member in guild.members:
                if member.bot:
                    continue
                rep = get_rep(member.id)
                # call silently to avoid per-user logging
                coro = _call_update_rep_role_silent(member, rep)
                if asyncio.iscoroutine(coro):
                    await coro
        print("Rep nickname refresh completed.")
        await asyncio.sleep(3600)  # Wait 1 hour

@bot.event
async def on_ready():
    try:
        print(f'Logged in as {bot.user}')
        await bot.tree.sync()
        print("Slash commands synced.")
        print("Bot is ready and all startup sections completed successfully.")

        # REMOVE nickname refresh on startup
        # for guild in bot.guilds:
        #     print(f"Refreshing rep roles for guild: {guild.name}")
        #     for member in guild.members:
        #         if member.bot:
        #             continue
        #         rep = get_rep(member.id)
        #         await update_rep_role(member, rep)
        # print("Rep roles refreshed for all members.")

        # Start periodic refresh task
        bot.loop.create_task(refresh_rep_nicknames())

        # Ensure sticky message if configured
        try:
            await ensure_sticky_message()
        except Exception:
            pass

    except Exception as e:
        print("Error in on_ready:", e)

# Sticky message config
STICKY_CHANNEL_ID = int(config.get('sticky_channel_id', 0))
last_sticky_message_id = None

async def send_sticky_message(channel):
    global last_sticky_message_id
    content = (
        "[REP-STICKY]\n"
        "**How to have rep counted correctly:**\n"
        "- Rate by mentioning the bot AND the user in the designated rep channel.\n"
        "- Include a clear rating phrase (e.g. `10/10`, `+1`, or `scammer`).\n"
        "- Do NOT rate yourself.\n"
        "- Make sure your rating message is NOT from a bot account and contains the mentioned user.\n"
        "- Edits to old posts may not trigger rechecks — reply with a proper rating message if needed.\n"
        "\nThis message is maintained by the bot and will always appear at the bottom."
    )
    try:
        if last_sticky_message_id:
            try:
                prev_msg = await channel.fetch_message(last_sticky_message_id)
                await prev_msg.delete()
            except Exception as e:
                print(f"Sticky: could not delete previous sticky message: {e}")
        sent = await channel.send(content)
        last_sticky_message_id = sent.id
    except Exception as e:
        print(f"Sticky: error sending sticky message: {e}")

# --- Slash Commands ---
@bot.tree.command(name="addrep", description="Admin: Add reputation points to a user")
async def addrep_command(interaction: discord.Interaction, user: discord.Member, amount: int):
    add_rep(user.id, amount)
    await interaction.response.send_message(f"Added {amount} rep to {user.display_name}!")

@bot.tree.command(name="ratings", description="Show a user's total reputation")
async def ratings_command(interaction: discord.Interaction, user: discord.Member):
    rep = get_rep(user.id)
    await interaction.response.send_message(f"{user.display_name} has {rep} reputation points.")

@bot.tree.command(name="leaderboard", description="Show the top 20 users with the most reputation")
async def leaderboard_command(interaction: discord.Interaction):
    admin_role_id = 1159251626389930045
    if not any(role.id == admin_role_id for role in getattr(interaction.user, "roles", [])):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    try:
        with sqlite3.connect("reviews.db") as conn:
            c = conn.cursor()
            c.execute('SELECT user_id, rep_total FROM rep_totals ORDER BY rep_total DESC LIMIT 20')
            rows = c.fetchall()
        if not rows:
            await interaction.response.send_message("No reputation data found.")
            return
        leaderboard = []
        for idx, (user_id, rep_total) in enumerate(rows, start=1):
            member = interaction.guild.get_member(user_id)
            name = member.display_name if member else f"User ID: {user_id}"
            leaderboard.append(f"{idx}. {name} — {rep_total} rep")
        msg = "**Top 20 Reputation Leaderboard:**\n" + "\n".join(leaderboard)
        await interaction.response.send_message(msg)
    except Exception as e:
        await interaction.response.send_message(f"Error fetching leaderboard: {e}", ephemeral=True)

print("Starting bot...")
bot.run(config['bot_token'])