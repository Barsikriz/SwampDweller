import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional


class Poll(commands.Cog):
    """Cog for polls command"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="poll", description="Create a poll")
    @app_commands.describe(
        question="Poll's question",
        option1="option #1",
        option2="option #2",
        option3="option #3",
        option4="option #4",
        option5="option #5",
        option6="option #6",
        option7="option #7",
        option8="option #8",
        option9="option #9",
        option10="option #10",
    )
    async def poll(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: Optional[str] = None,
        option3: Optional[str] = None,
        option4: Optional[str] = None,
        option5: Optional[str] = None,
        option6: Optional[str] = None,
        option7: Optional[str] = None,
        option8: Optional[str] = None,
        option9: Optional[str] = None,
        option10: Optional[str] = None,
    ):
        options = [
            o
            for o in [
                option1,
                option2,
                option3,
                option4,
                option5,
                option6,
                option7,
                option8,
                option9,
                option10,
            ]
            if o is not None
        ]

        if len(options) < 1:
            await interaction.response.send_message(
                "❌ Нужно минимум 1 вариант ответа на опрос.", ephemeral=True
            )
            return

        emoji_list = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        description_lines = []
        for i, option in enumerate(options):
            description_lines.append(f"{emoji_list[i]} {option}")

        embed = discord.Embed(
            title=f"📊 Опрос: {question}",
            description="\n".join(description_lines),
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"Опрос создан: {interaction.user}")

        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        for i in range(len(options)):
            await message.add_reaction(emoji_list[i])


async def setup(bot: commands.Bot):
    await bot.add_cog(Poll(bot))
