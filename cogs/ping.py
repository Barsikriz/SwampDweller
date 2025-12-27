import discord
import time
from discord.ext import commands
from discord import app_commands


class Ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping")
    async def ping(self, interaction: discord.Interaction):
        ws_ping = round(self.bot.latency * 1000, 2)

        start = time.perf_counter()
        message = await interaction.response.send_message("Измеряю", ephemeral=True)
