import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
import asyncio
import os
import logging
from datetime import datetime
import re

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Настройки бота
TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = '!'
TARGET_URL = os.getenv('TARGET_URL', 'https://wargm.ru/server/79795')
UPDATE_INTERVAL = int(os.getenv('UPDATE_INTERVAL', 300))

# Создание бота
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

def get_player_count():
    """Получение количества игроков с сайта"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(TARGET_URL, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем элемент с игроками (специально для вашего сайта)
        element = soup.find('span', class_=['c-green', 'fw-b'])
        
        if element:
            text = element.text
            logger.info(f"Найден текст: {text}")  # Для отладки
            match = re.search(r'(\d+)/(\d+)', text)
            if match:
                current = int(match.group(1))
                logger.info(f"Найдено игроков: {current}")
                return current
        logger.warning("Элемент не найден")
        return None
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return None

@tasks.loop(minutes=5)
async def update_status():
    """Автообновление статуса"""
    count = get_player_count()
    if count:
        await bot.change_presence(activity=discord.Game(name=f"🎮 {count} игроков"))
        logger.info(f"Статус обновлен: {count}")

@bot.event
async def on_ready():
    logger.info(f'✅ Бот {bot.user} запущен!')
    logger.info(f'ID бота: {bot.user.id}')
    logger.info(f'URL сайта: {TARGET_URL}')
    update_status.start()

@bot.command(name='players')
async def players(ctx):
    """Показать количество игроков"""
    async with ctx.typing():
        count = get_player_count()
        if count:
            embed = discord.Embed(
                title="🎮 Игроки онлайн",
                description=f"**{count}**",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Запросил: {ctx.author.name}")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Не удалось получить данные",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

@bot.command(name='test')
@commands.has_permissions(administrator=True)
async def test(ctx):
    """Тест парсера (только для админов)"""
    try:
        response = requests.get(TARGET_URL)
        soup = BeautifulSoup(response.text, 'html.parser')
        element = soup.find('span', class_=['c-green', 'fw-b'])
        
        if element:
            await ctx.send(f"✅ Найдено: {element.text}")
        else:
            await ctx.send("❌ Ничего не найдено")
            
        # Показываем первые 500 символов страницы для отладки
        await ctx.send(f"```\n{response.text[:500]}...\n```")
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}")

@bot.command(name='ping')
async def ping(ctx):
    """Проверка работы бота"""
    await ctx.send(f'🏓 Понг! {round(bot.latency * 1000)}мс')

@bot.command(name='help_custom')
async def help_custom(ctx):
    """Справка"""
    embed = discord.Embed(title="📚 Команды", color=discord.Color.blue())
    embed.add_field(name="!players", value="Показать игроков", inline=False)
    embed.add_field(name="!ping", value="Проверка связи", inline=False)
    embed.add_field(name="!test", value="Тест парсера (админ)", inline=False)
    await ctx.send(embed=embed)

if __name__ == "__main__":
    if not TOKEN:
        logger.error("❌ Нет токена! Добавьте DISCORD_TOKEN в переменные окружения Railway")
        exit(1)
    bot.run(TOKEN)
