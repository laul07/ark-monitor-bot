import discord
from discord.ext import commands
import asyncio
import os
from settings import BOT_TOKEN

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot is ready: {bot.user}")
    try:
        synced = await bot.tree.sync()  # Global sync
        print("🔧 Slash commands synchronized:")
        for cmd in synced:
            print(f"   • /{cmd.name} - {cmd.description}")
        print(f"✅ Total synced: {len(synced)} command(s).")
    except Exception as e:
        print(f"❌ Command sync failed: {e}")

@bot.command()
async def listslash(ctx):
    commands_list = [cmd.name for cmd in bot.tree.get_commands()]
    await ctx.send(f"🔍 Slash commands loaded: {', '.join(commands_list)}")

@bot.event
async def on_command_error(ctx, error):
    print(f"[COMMAND ERROR] {ctx.command} failed: {error}")

@bot.event
async def on_application_command(ctx):
    print(f"[SLASH] /{ctx.command.name} used by {ctx.user} in {ctx.guild.name}")

async def main():
    for filename in os.listdir("./cogs/slash"):
        if filename.endswith(".py") and filename != "__init__.py":
            extension = f"cogs.slash.{filename[:-3]}"
            try:
                await bot.load_extension(extension)
                print(f"🔌 Loaded: {extension}")
            except Exception as e:
                print(f"⚠️ Failed to load {extension}: {e}")

    await bot.start(BOT_TOKEN)

asyncio.run(main())
