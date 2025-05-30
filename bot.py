import discord
from discord.ext import commands
import asyncio
import os
from settings import BOT_TOKEN
import logging

logging.basicConfig(level=logging.INFO)

intents = discord.Intents(guilds=True, messages=True, message_content=True)
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    logging.info(f"✅ Bot is ready: {bot.user}")
    try:
        synced = await bot.tree.sync()  # Global sync
        logging.info("🔧 Slash commands synchronized:")
        for cmd in synced:
            logging.info(f"   • /{cmd.name} - {cmd.description}")
        logging.info(f"✅ Total synced: {len(synced)} command(s).")
    except Exception as e:
        logging.error(f"❌ Command sync failed: {e}")

@bot.command()
async def listslash(ctx):
    commands_list = [cmd.name for cmd in bot.tree.get_commands()]
    await ctx.send(f"🔍 Slash commands loaded: {', '.join(commands_list)}")

@bot.command()
@commands.is_owner()
async def load(ctx, extension):
    try:
        await bot.load_extension(extension)
        await ctx.send(f"✅ Loaded: {extension}")
    except Exception as e:
        await ctx.send(f"❌ Failed to load {extension}: {e}")

@bot.command()
@commands.is_owner()
async def unload(ctx, extension):
    try:
        await bot.unload_extension(extension)
        await ctx.send(f"✅ Unloaded: {extension}")
    except Exception as e:
        await ctx.send(f"❌ Failed to unload {extension}: {e}")

@bot.event
async def on_command_error(ctx, error):
    logging.error(f"[COMMAND ERROR] {ctx.command} failed: {error}")

@bot.event
async def on_application_command(ctx):
    logging.info(f"[SLASH] /{ctx.command.name} used by {ctx.user} in {ctx.guild.name}")

async def main():
    for filename in os.listdir("./cogs/slash"):
        if filename.endswith(".py") and filename != "__init__.py":
            extension = f"cogs.slash.{filename[:-3]}"
            try:
                await bot.load_extension(extension)
                logging.info(f"🔌 Loaded: {extension}")
            except Exception as e:
                logging.error(f"⚠️ Failed to load {extension}: {e}")

    await bot.start(BOT_TOKEN)

asyncio.run(main())
