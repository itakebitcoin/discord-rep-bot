# Discord Reputation Bot

A Discord bot for managing user reputation, reviews, and automated thread moderation in a server. This bot is designed for communities that want to track user reputation, enforce posting rules, and provide feedback mechanisms.

## Features

- **Reputation System:** Users can give and receive reputation points (+1/-1) by mentioning the bot and another user in a designated channel.
- **Review Tracking:** Stores and displays user reviews and reputation totals.
- **Automated Thread Moderation:** Monitors forum threads for required information (price, location/city) and applies tags or sends notifications if info is missing.
- **Role Management:** Automatically updates user roles based on reputation.
- **Sticky Instructions:** Maintains a sticky message in the review channel with instructions for proper rep submissions.
- **Admin Commands:** Includes slash commands for admins to adjust reputation, view leaderboards, and enable/disable moderation features.
- **Configurable:** All important IDs, tag names, and filenames are set in `config.json` for easy setup.

## Setup

1. **Clone the Repository**
   ```sh
   git clone https://github.com/itakebitcoin/discord-rep-bot.git
   cd discord-rep-bot
   ```

2. **Install Requirements**
   ```sh
   pip install -r requirements.txt
   ```

3. **Configure the Bot**
   - Edit `config.json` and fill in your bot token, channel IDs, tag names, and other settings. Example:
     ```json
     {
         "bot_token": "YOURTOKENHERE",
         "target_channel_id": "ID of the channel for rep messages",
         "forum_channel_id": "ID of the forum channel for threads",
         "missing_price_tag_name": "Missing Price",
         "missing_location_tag_name": "Missing Location",
         "log_channel_id": "ID of the log channel",
         "sticky_channel_id": "ID of the reviews channel (for sticky message)"
     }
     ```
   - Create a `cities.txt` file listing all cities to be checked for location info (one per line).

4. **Run the Bot**
   ```sh
   python review.py
   ```

## Usage

- **Giving Rep:**
  - In the designated rep channel, mention the bot and the user you want to rate.
  - Include a clear rating phrase (e.g., `10/10`, `+1`, `scammer`).
  - The bot will update the user's reputation and role accordingly.

- **Thread Moderation:**
  - When a new thread is created in the forum channel, the bot checks for price and city in the title.
  - If missing, it applies tags and sends a notification to the thread owner.
  - Owners can reply to the bot's notification after editing their post to remove tags.

- **Admin Commands:**
  - `/addrep <user> <amount>`: Add reputation points to a user.
  - `/ratings <user>`: Show a user's total reputation.
  - `/leaderboard`: Show the top 20 users with the most reputation.
  - `/forumchecker <enable|disable>`: Enable or disable thread moderation.

## File Structure

- `review.py`: Main bot logic and event handlers.
- `forum_checker.py`: Thread moderation and tag management.
- `rep_roles.py`: Role management based on reputation.
- `utils.py`: Utility functions for config and ratings file management.
- `config.json`: All configuration values (IDs, tag names, filenames).
- `cities.txt`: List of cities for location checking.
- `requirements.txt`: Python dependencies.
- `reviews.db`: SQLite database for reputation storage.

## Contributing

Pull requests and suggestions are welcome! Please open an issue for bugs or feature requests.

## License

MIT License. See `LICENSE` for details.

## Credits

Developed by ITAKEBITCOIN. Inspired by Discord community needs for reputation and review management.
