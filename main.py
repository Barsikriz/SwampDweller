from discord import app_commands
import os
import discord
from dotenv import load_dotenv
from discord.ext import commands
import yt_dlp
import asyncio
from typing import Optional
from collections import deque

load_dotenv()
token = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

bot.commands_synced = False

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,  # Убирает лишние предупреждения в консоль
    "extract_flat": False,  # Важно: должен быть False, чтобы получить полную информацию
    "force_generic_extractor": False,
    # Параметры для обхода ограничений
    "socket_timeout": 30,
    "extractor_retries": 3,
    "fragment_retries": 10,
    "ignoreerrors": True,
}
FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",  # Только аудио
}


class MusicPlayer:
    "класс для управления музыкой на одном сервере"

    def __init__(self) -> None:
        self.queue = deque()
        self.current_track = None
        self.loop_mode = "off"
        self.is_playing = False
        self.voice_client = None

    def add_to_queue(self, track_info):
        """Добавляет трек в очередь"""
        self.queue.append(track_info)
        return len(self.queue)

    def get_next_track(self):
        "запуск следующего трека"
        if self.loop_mode == "track" and self.current_track:
            return self.current_track

        if not self.queue:
            self.current_track = None
            return None

        if self.queue:
            self.current_track = self.queue.popleft()

            if self.loop_mode == "queue":
                self.queue.append(self.current_track.copy())
        return self.current_track

    def skip_track(self):
        "пропуск трека"
        if self.loop_mode == "track":
            return self.current_track

        if self.queue:
            self.current_track = self.queue.popleft()
            if self.loop_mode == "queue" and self.current_track:
                self.queue.append(self.current_track.copy())
            return self.current_track

        else:
            self.current_track == None
            return None

    def clear_queue(self):
        "очистка очереди"
        self.queue.clear()

    def toggle_loop(self, mode="track"):
        "переключене режима цикла"
        modes = ["off", "track", "queue"]
        if mode in modes and mode is not None:
            self.loop_mode = mode
        else:
            current_index = (
                modes.index(self.loop_mode) if self.loop_mode in modes else 0
            )
            next_index = (current_index + 1) % len(modes)
            self.loop_mode = modes[next_index]
        return self.loop_mode


async def start_playback(guild_id, text_channel=None):
    player = get_music_player(guild_id)

    if not player.voice_client or not player.voice_client.is_connected():
        return

    player.is_playing = True

    while player.is_playing:
        track = player.get_next_track()
        if not track:
            player.is_playing = False
            break

        source = discord.FFmpegPCMAudio(track["url"], **FFMPEG_OPTIONS)
        player.voice_client.play(source)

        if text_channel:
            embed = discord.Embed(
                title="🎶 Сейчас играет",
                description=f"**{track['title']}**",
                color=discord.Color.green(),
            )
            embed.add_field(
                name="Длительность", value=format_duration(track["duration"])
            )
            embed.add_field(name="Запросил", value=track["requester"])
            embed.add_field(name="Режим повтора", value=player.loop_mode, inline=False)
            embed.set_footer(text=f"Треков в очереди: {len(player.queue)}")
            await text_channel.send(embed=embed)

        while player.voice_client.is_playing():
            await asyncio.sleep(1)

    await asyncio.sleep(300)
    if player.voice_client and not player.voice_client.is_playing():
        await player.voice_client.disconnect()
        player.is_playing = False


def format_duration(seconds):
    seconds = int(seconds)
    if not seconds:
        return "Неизвестно"
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"


music_players = {}


def get_music_player(guild_id):
    "Получает или создает плеер для сервера"
    if guild_id not in music_players:
        music_players[guild_id] = MusicPlayer()
    return music_players[guild_id]


@bot.tree.command(name="ping", description="Проверка работоспособности бота")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Понг!")


@bot.tree.command(name="poll")
async def poll(
    interaction: discord.Interaction,
    question: str,
    option1: str,
    option2: Optional[str] = None,
    option3: Optional[str] = None,
    option4: Optional[str] = None,
):
    options = [opt for opt in [option1, option2, option3, option4] if opt is not None]

    if len(options) < 1 or len(options) > 10:
        await interaction.response.send_message(
            "Укажите от 1 до 2 вариантов ответа", ephemeral=True
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
    embed.set_footer(text=f"Опрос ссоздан: {interaction.user}")

    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()
    for i in range(len(options)):
        await message.add_reaction(emoji_list[i])


@bot.tree.command(name="play", description="Воспроизвести трек по названию")
async def play(interaction: discord.Interaction, query: str):
    if not interaction.user.voice:
        return await interaction.response.send_message(
            "❌ Вы должны находиться в голосовом канале!", ephemeral=True
        )

    await interaction.response.defer()

    # Получаем плеер для сервера
    player = get_music_player(interaction.guild_id)

    # 1. Поиск трека и получение прямого аудиопотока
    loop = asyncio.get_event_loop()
    try:
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            # Поиск видео
            search_info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(f"ytsearch:{query}", download=False)
            )
            if not search_info or "entries" not in search_info:
                await interaction.followup.send("❌ Ничего не найдено.")
                return

            video_url = search_info["entries"][0]["url"]
            video_title = search_info["entries"][0]["title"]

            # Получение детальной информации и аудиоформатов
            detailed_info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(video_url, download=False)
            )

            if "formats" not in detailed_info:
                await interaction.followup.send("❌ Не удалось получить аудиопоток.")
                return

            audio_formats = [
                f for f in detailed_info["formats"] if f.get("acodec") != "none"
            ]
            if not audio_formats:
                await interaction.followup.send("❌ Аудиоформаты не найдены.")
                return

            best_audio = max(audio_formats, key=lambda f: f.get("abr", 0) or 0)
            audio_url = best_audio["url"]

            duration_sources = [
                detailed_info.get("duration"),
                detailed_info.get("approx_duration"),
                search_info["entries"][0].get["duration"],
                0,
            ]

            duration = next((d for d in duration_sources if d), 0)

            track_info = {
                "url": audio_url,
                "title": video_title,
                "duration": duration,
                "requester": interaction.user.name,
            }

    except Exception as e:
        await interaction.followup.send(f"❌ Ошибка при получении аудио: {e}")
        return

    # 2. Подключение к голосовому каналу
    voice_channel = interaction.user.voice.channel
    try:
        if interaction.guild.voice_client is None:
            player.voice_client = await voice_channel.connect()
        else:
            player.voice_client = interaction.guild.voice_client
            if player.voice_client.channel != voice_channel:
                await player.voice_client.move_to(voice_channel)
    except Exception as e:
        await interaction.followup.send(f"❌ Ошибка подключения: {e}")
        return

    # 3. Добавление трека в очередь
    queue_position = player.add_to_queue(track_info)

    # 4. Если ничего не играет, запускаем воспроизведение
    if not player.is_playing:
        await interaction.followup.send(
            f"🎶 Добавлено в очередь (#{queue_position}): **{track_info['title']}**"
        )
        # Запускаем цикл воспроизведения в фоне
        asyncio.create_task(start_playback(interaction.guild_id, interaction.channel))
    else:
        await interaction.followup.send(
            f"✅ Добавлено в очередь (#{queue_position}): **{track_info['title']}**"
        )


@bot.tree.command(
    name="stop",
    description="Остановить воспроизведение и заставить бота выйти из канала",
)
async def stop_command(interaction: discord.Interaction):
    player = get_music_player(guild_id)
    if player.voice_client:
        player.clear_queue()
        player.is_playing = False
        if player.voice_client.is_playing():
            player.voice_client.stop()
        await player.voice_client.disconnect()
        await interaction.response.send_message(
            "⏹️ Воспроизведение остановлено, очередь очищена."
        )
    else:
        await interaction.response.send_message(
            "❌ Бот не в голосовом канале.", ephemeral=True
        )


@bot.tree.command(name="skip", description="Пропустить текущий трек")
async def skip(interaction: discord.Interaction):
    player = get_music_player(interaction.guild_id)

    if not player.voice_client or not player.voice_client.is_playing():
        await interaction.response.send_message(
            "❌ Сейчас ничего не играет.", ephemeral=True
        )
        return

    if len(player.queue) == 0 and player.loop_mode == "off":
        player.voice_client.stop()
        return
    player.voice_client.stop()

    await interaction.response.send_message("⏭️ Трек пропущен.")


@bot.tree.command(name="loop", description="Переключить или установить режим повтора")
@app_commands.choices(
    mode=[
        app_commands.Choice(name="🔁 Выкл", value="off"),
        app_commands.Choice(name="🔂 Трек", value="track"),
        app_commands.Choice(name="♻️ Очередь", value="queue"),
    ]
)
async def loop_command(
    interaction: discord.Interaction, mode: Optional[app_commands.Choice[str]] = None
):
    player = get_music_player(interaction.guild_id)

    if mode:
        # Если пользователь выбрал вариант, устанавливаем его
        new_mode = mode.value
        player.loop_mode = new_mode  # Просто устанавливаем
    else:
        # Если вызвали без аргумента, переключаем по кругу
        new_mode = player.toggle_loop()

    # Отправляем результат
    modes_descriptions = {
        "off": "Режим повтора выключен",
        "track": "🔂 Повтор текущего трека",
        "queue": "🔁 Повтор всей очереди",
    }
    await interaction.response.send_message(
        embed=discord.Embed(
            title="Режим повтора",
            description=modes_descriptions[new_mode],
            color=discord.Color.blue(),
        )
    )


@bot.tree.command(name="queue", description="Показать текущую очередь")
async def show_queue(interaction: discord.Interaction):
    player = get_music_player(interaction.guild_id)

    embed = discord.Embed(
        title="📋 Очередь воспроизведения", color=discord.Color.gold()
    )

    if player.current_track:
        embed.add_field(
            name="🎶 Сейчас играет",
            value=f"**{player.current_track['title']}**\n"
            f"Запросил: {player.current_track['requester']}",
            inline=False,
        )

    if player.queue:
        queue_list = []
        for i, track in enumerate(
            list(player.queue)[:10], 1
        ):  # Показываем первые 10 треков
            queue_list.append(f"**{i}.** {track['title']} ({track['requester']})")

        embed.add_field(
            name=f"Треков в очереди: {len(player.queue)}",
            value="\n".join(queue_list) if queue_list else "Очередь пуста",
            inline=False,
        )
    else:
        embed.add_field(name="Очередь", value="📭 Очередь пуста", inline=False)

    embed.add_field(name="Режим повтора", value=player.loop_mode, inline=True)

    await interaction.response.send_message(embed=embed)


@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id:
        return

    if before.channel and before.channel.guild.voice_client:
        voice_client = before.channel.guild.voice_client

        if len(voice_client.channel.members) == 1:
            player = get_music_player(before.channel.guild.id)
            player.clear_queue()
            player.is_playing = False
            await voice_client.disconnect()


@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to the server!")

    test_guild_id = 1246407847357448192  # ID вашего сервера (гильдии)
    test_guild = discord.Object(id=test_guild_id)

    if not getattr(bot, "commands_synced", False):
        print(f"🔄 Пытаюсь синхронизировать команды с сервером ID: {test_guild_id}")
        try:
            # Синхронизируем только с тестовым сервером
            synced = await bot.tree.sync()

            if synced:
                print(f"✅ УСПЕХ! Синхронизировано {len(synced)} команд:")
                for cmd in synced:
                    print(f"   - /{cmd.name}")
            else:
                print("⚠️  Синхронизация прошла, но список команд пуст.")
                print("   Возможные причины:")
                print("   1. Бот не имеет прав 'applications.commands' на сервере")
                print("   2. На сервере уже есть 50+ слэш-команд (лимит Discord)")
                print("   3. Ошибка в объявлении команд (декораторы @bot.tree.command)")

            # Устанавливаем флаг, чтобы не синхронизировать повторно
            bot.commands_synced = True

        except discord.errors.HTTPException as e:
            if e.status == 429:
                retry_after = e.response.headers.get("Retry-After", "неизвестно")
                print(
                    f"⏳ Discord ограничивает запросы. Попробуйте снова через {retry_after} сек."
                )
                print("   Рекомендация: подождите 1-2 часа перед следующим запуском.")
            else:
                print(f"❌ Ошибка HTTP при синхронизации: {e}")
        except Exception as e:
            print(f"❌ Неожиданная ошибка: {type(e).__name__}: {e}")
    else:
        print("ℹ️  Команды уже были синхронизированы в этой сессии.")


bot.run(token)
