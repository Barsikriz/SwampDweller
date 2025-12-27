# main.py - ТОЛЬКО ЭТО
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)


@bot.event
async def on_ready():
    print(f"{bot.user} запущен!")

    # Автозагрузка всех когов
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"✅ Загружен: {filename}")
            except Exception as e:
                print(f"❌ Ошибка загрузки {filename}: {e}")

    # Синхронизация команд
    try:
        synced = await bot.tree.sync()
        print(f"🔗 Синхронизировано {len(synced)} команд")
        for cmd in synced:
            print(f"   - /{cmd.name}")
    except Exception as e:
        print(f"⚠️ Ошибка синхронизации: {e}")


bot.run(os.getenv("DISCORD_TOKEN"))
