import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import logging
import json
import aiohttp

load_dotenv()
TOKEN = os.getenv('TOKEN')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s',
    handlers=[
        logging.FileHandler(filename='bot.log', encoding='utf-8', mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('discord')

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    try:
        synced = await bot.tree.sync()
        logger.info(f'Successfully synced {len(synced)} commands.')
    except Exception as e:
        logger.error(f'Error syncing commands: {e}')
    logger.info('------')

async def fetch_avatar_bytes(url: str) -> bytes:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.read()
            else:
                logger.error(f'Failed to fetch avatar from {url}, status code: {response.status}')
                return None

async def autocomplete_target(interaction: discord.Interaction, current: str):
    guild = interaction.guild
    if not guild:
        return []
    choices = [
        app_commands.Choice(
            name=f"{member.display_name} ({member.name})", 
            value=str(member.id)
        )
        for member in guild.members
        if member.display_name.lower().startswith(current.lower()) and not member.bot
    ]
    return choices[:25]

@bot.tree.command(name="impersonate", description="Send a message as another user.")
@app_commands.describe(
    target="The user you want to impersonate.",
    message="The message you want to send as the specified user."
)
@app_commands.autocomplete(target=autocomplete_target)
async def impersonate(interaction: discord.Interaction, target: str, message: str):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    if not guild:
        await interaction.followup.send("This command can only be used within a server.", ephemeral=True)
        return

    try:
        user_id = int(target)
        target_member = guild.get_member(user_id)
        if not target_member:
            await interaction.followup.send("User not found.", ephemeral=True)
            return
    except ValueError:
        await interaction.followup.send("Invalid user selection.", ephemeral=True)
        return

    channel = interaction.channel
    if not isinstance(channel, discord.TextChannel):
        await interaction.followup.send("This command can only be used in text channels.", ephemeral=True)
        return

    try:
        avatar_url = target_member.display_avatar.url
        avatar_bytes = await fetch_avatar_bytes(avatar_url)
        if not avatar_bytes:
            avatar_bytes = None

        webhook = await channel.create_webhook(
            name=target_member.display_name,
            avatar=avatar_bytes,
            reason=f"Impersonation by {interaction.user}"
        )
        await webhook.send(
            message,
            username=target_member.display_name,
            avatar_url=avatar_url
        )
        await webhook.delete()
        await interaction.followup.send(f'Message sent as {target_member.display_name}.', ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("I don't have permission to manage webhooks in this channel.", ephemeral=True)
    except discord.HTTPException as e:
        logger.error(f"HTTPException: {e}")
        await interaction.followup.send("An error occurred while sending the message.", ephemeral=True)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        await interaction.followup.send("An unexpected error occurred.", ephemeral=True)

bot.run(TOKEN)
