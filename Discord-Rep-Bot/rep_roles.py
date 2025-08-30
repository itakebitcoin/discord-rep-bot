import discord
import re  # Import re module for regular expression operations

# Change the role IDs below to match your server's roles. The format is (threshold, role_id). So when someone hits 5 rep, they get the Starter role, at 20 they get Positive, and at 100 they get Trusted.

# Example thresholds and role IDs (replace with your actual role IDs)
ROLE_THRESHOLDS = [
    (100, 123456),  # Trusted role 
    (20, 123456),  # Positive role
    (5, 123456),  # Starter role
]

async def update_rep_role(member: discord.Member, rep: int):
    """
    Assigns or removes roles based on the user's reputation.
    Only the highest qualifying role is assigned.
    Updates the member's nickname to include their rep in the format: Name (25 rep), but only if rep > 0.
    Does NOT change nickname for users with 0 rep.
    """
    # Remove all rep roles first
    for _, role_id in ROLE_THRESHOLDS:
        role = member.guild.get_role(role_id)
        if role and role in member.roles:
            try:
                await member.remove_roles(role)
            except Exception as e:
                print(f"Error removing role {role.name} from {member.display_name}: {e}")

    # Assign the highest role they qualify for
    for threshold, role_id in sorted(ROLE_THRESHOLDS, reverse=True):
        if rep >= threshold:
            role = member.guild.get_role(role_id)
            if role and role not in member.roles:
                try:
                    await member.add_roles(role)
                    print(f"Assigned role {role.name} to {member.display_name}")
                except Exception as e:
                    print(f"Error assigning role {role.name} to {member.display_name}: {e}")
            break

    # Only update nickname if rep > 0
    if rep > 0:
        base_nick = member.display_name
        base_nick = re.sub(r"\s*\(\d+\s*rep\)$", "", base_nick)
        new_nick = f"{base_nick} ({rep} rep)"
        try:
            await member.edit(nick=new_nick)
            print(f"Updated nickname for {member.display_name} to {new_nick}")
        except Exception as e:
            print(f"Error updating nickname for {member.display_name}: {e}")