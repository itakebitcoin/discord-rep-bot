import re
import discord
import time

# --- Utility Functions ---

def compile_city_patterns(cities):
    """
    Compile regex patterns for each city for efficient matching.
    """
    return [re.compile(rf"\b{re.escape(city.lower())}\b") for city in cities]

def has_price(text):
    """
    Returns True if the text contains a price pattern like $300, 300$, or keywords indicating free.
    """
    lowered = text.lower()
    price_pattern = r"(\$\s*\d+|\d+\s*\$)"
    free_keywords = ["for free", "freebie", "free", "0 dollars", "$0", "0$", "no charge", "no cost"]
    if re.search(price_pattern, text):
        return True
    if any(keyword in lowered for keyword in free_keywords):
        return True
    return False

def has_city(text, city_patterns):
    """
    Returns True if the text contains a whole word match for any city.
    """
    lowered = text.lower()
    return any(pattern.search(lowered) for pattern in city_patterns)

# --- Notification Tracking with Cleanup ---

class NotifiedThreads:
    """
    Tracks threads that have been notified, with optional expiry for cleanup.
    """
    def __init__(self, expiry_seconds=86400):  # 24 hours default
        self.data = {}
        self.expiry_seconds = expiry_seconds

    def set(self, thread_id, notification_id):
        self.data[thread_id] = (notification_id, time.time())

    def get(self, thread_id):
        entry = self.data.get(thread_id)
        if entry:
            notification_id, timestamp = entry
            # Clean up expired entries
            if time.time() - timestamp > self.expiry_seconds:
                del self.data[thread_id]
                return None
            return notification_id
        return None

    def pop(self, thread_id):
        if thread_id in self.data:
            del self.data[thread_id]

    def cleanup(self):
        now = time.time()
        expired = [tid for tid, (_, ts) in self.data.items() if now - ts > self.expiry_seconds]
        for tid in expired:
            del self.data[tid]

# --- Tag Update Helper ---

async def update_tags(thread, price_found, location_found, missing_price_tag, missing_location_tag):
    """
    Updates tags on the thread based on price/location presence.
    Returns the updated tag list.
    """
    current_tags = list(thread.applied_tags)
    updated_tags = current_tags.copy()

    if price_found and missing_price_tag in updated_tags:
        updated_tags.remove(missing_price_tag)
    elif not price_found and missing_price_tag and missing_price_tag not in updated_tags:
        updated_tags.append(missing_price_tag)

    if location_found and missing_location_tag in updated_tags:
        updated_tags.remove(missing_location_tag)
    elif not location_found and missing_location_tag and missing_location_tag not in updated_tags:
        updated_tags.append(missing_location_tag)

    if set(updated_tags) != set(current_tags):
        try:
            await thread.edit(applied_tags=updated_tags)
            print(f"Updated tags for thread {thread.id}: {updated_tags}")
        except Exception as e:
            print(f"Failed to update tags for thread {thread.id}: {e}")

    return updated_tags

# --- Main Handler ---

async def handle_thread_message(
    message,
    forum_channel_id,
    missing_price_tag_name,
    missing_location_tag_name,
    cities,
    notified_threads_obj
):
    """
    Handles replies in threads:
    - If OP posts their first message, checks for price/location and sends ONE notification if missing.
    - If OP replies to the bot's notification, rechecks and updates tags/notifications.
    - Only sends a new notification if the OP replies to the bot's last notification.
    - If the thread is older than 1 day, do not re-flag or re-notify.
    """
    city_patterns = compile_city_patterns(cities)

    # --- OP's first message in the thread ---
    if (
        isinstance(message.channel, discord.Thread)
        and message.channel.parent_id == forum_channel_id
        and message.author.id == message.channel.owner_id
        and not message.author.bot
        and message.channel.id not in notified_threads_obj.data  # Only notify once
    ):
        # Optimization: Don't process threads older than 1 day
        thread_age = time.time() - message.channel.created_at.timestamp()
        if thread_age > 86400:
            print(f"Thread {message.channel.id} is older than 1 day. Skipping notification/tag logic.")
            return

        tags = message.channel.parent.available_tags
        missing_price_tag = discord.utils.get(tags, name=missing_price_tag_name)
        missing_location_tag = discord.utils.get(tags, name=missing_location_tag_name)

    price_found = has_price(message.channel.name) or has_price(message.content)
    location_found = has_city(message.channel.name, city_patterns) or has_city(message.content, city_patterns)

        updated_tags = await update_tags(message.channel, price_found, location_found, missing_price_tag, missing_location_tag)

        missing = []
        if missing_price_tag in updated_tags and not price_found:
            missing.append("a price")
        if missing_location_tag in updated_tags and not location_found:
            missing.append("a location (city)")
        if missing:
            try:
                notification = await message.channel.send(
                    f"{message.author.mention}, your post is missing {', and '.join(missing)} in the title or message. "
                    "Please edit the thread title or message to include the missing info, then reply to this message to remove the tags."
                )
                notified_threads_obj.set(message.channel.id, notification.id)
                print(f"Sent notification in thread {message.channel.id}")
            except Exception as e:
                print(f"Failed to send notification in thread {message.channel.id}: {e}")

    # --- Only send another notification if OP replies to the bot's last notification ---
    if (
        isinstance(message.channel, discord.Thread)
        and message.channel.parent_id == forum_channel_id
        and not message.author.bot
    ):
        thread = message.channel
        # Optimization: Don't process threads older than 1 day
        thread_age = time.time() - thread.created_at.timestamp()
        if thread_age > 86400:
            print(f"Thread {thread.id} is older than 1 day. Skipping notification/tag logic.")
            return

        notification_id = notified_threads_obj.get(thread.id)
        if (
            message.reference
            and message.reference.message_id == notification_id
        ):
            tags = thread.parent.available_tags
            missing_price_tag = discord.utils.get(tags, name=missing_price_tag_name)
            missing_location_tag = discord.utils.get(tags, name=missing_location_tag_name)

            starter_message = thread.starter_message
            price_found = has_price(thread.name)
            location_found = has_norcal_city(thread.name, city_patterns)
            if starter_message:
                price_found = price_found or has_price(starter_message.content)
                location_found = location_found or has_norcal_city(starter_message.content, city_patterns)
            price_found = price_found or has_price(message.content)
            location_found = location_found or has_city(message.content, city_patterns)

            updated_tags = await update_tags(thread, price_found, location_found, missing_price_tag, missing_location_tag)

            missing = []
            if not price_found and missing_price_tag in updated_tags:
                missing.append("a price")
            if not location_found and missing_location_tag in updated_tags:
                missing.append("a location (city)")

            try:
                if not missing:
                    await thread.send(f"{message.author.mention}, all required info found! Tags removed. Thank you.")
                    notified_threads_obj.pop(thread.id)
                    print(f"All info found for thread {thread.id}, notification removed.")
                else:
                    notification = await thread.send(
                        f"{message.author.mention}, your post is still missing {', and '.join(missing)} in the title or message. "
                        "Please edit the thread title or message and reply **directly to this message** for me to recheck. If you have already provided the info."
                    )
                    notified_threads_obj.set(thread.id, notification.id)
                    print(f"Sent follow-up notification in thread {thread.id}")
            except Exception as e:
                print(f"Failed to send follow-up notification in thread {thread.id}: {e}")

    # Periodically clean up old notifications
    notified_threads_obj.cleanup()

async def handle_thread_create(
    thread,
    forum_channel_id,
    missing_price_tag_name,
    missing_location_tag_name,
    cities
):
    """
    Handles new forum threads:
    - Checks for price and location in the title.
    - Adds missing tags if info is not found.
    """
    city_patterns = compile_city_patterns(cities)

    if thread.parent_id != forum_channel_id:
        return

    tags = thread.parent.available_tags
    current_tags = list(thread.applied_tags)

    missing_price_tag = discord.utils.get(tags, name=missing_price_tag_name)
    missing_location_tag = discord.utils.get(tags, name=missing_location_tag_name)

    price_found = has_price(thread.name)
    location_found = has_city(thread.name, city_patterns)

    updated_tags = current_tags.copy()
    if not price_found and missing_price_tag and missing_price_tag not in updated_tags:
        updated_tags.append(missing_price_tag)
    if not location_found and missing_location_tag and missing_location_tag not in updated_tags:
        updated_tags.append(missing_location_tag)

    if set(updated_tags) != set(current_tags):
        try:
            await thread.edit(applied_tags=updated_tags)
            print(f"Initial tags set for thread {thread.id}: {updated_tags}")
        except Exception as e:
            print(f"Failed to set initial tags for thread {thread.id}: {e}")