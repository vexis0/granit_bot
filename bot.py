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

# ID роли для автоматической выдачи
AUTO_ROLE_ID = int(os.getenv('AUTO_ROLE_ID', 0))

# Создание бота
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

def get_player_info():
    """
    Получение информации об игроках (текущие / максимум)
    Возвращает: (current, max) или (None, None) если не найдено
    """
    try:
        # Сначала пробуем API (надежнее)
        api_url = "https://api.scpslgame.com/serverinfo.php?id=79795&players=true"
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data and "Servers" in data and len(data["Servers"]) > 0:
                server = data["Servers"][0]
                players_str = server.get("Players", "0/0")
                
                if "/" in players_str:
                    current = int(players_str.split("/")[0])
                    maximum = int(players_str.split("/")[1])
                    logger.info(f"✅ API: {current}/{maximum}")
                    return (current, maximum)
        
        # Если API не сработал, пробуем парсинг сайта
        logger.info("⚠️ API не сработал, пробуем парсинг...")
        response = requests.get(TARGET_URL, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем элемент с игроками
        element = soup.find('span', class_=['c-green', 'fw-b'])
        
        if element:
            text = element.text
            logger.info(f"🔍 Найден текст: {text}")
            
            # Ищем паттерн "число/число"
            match = re.search(r'(\d+)/(\d+)', text)
            if match:
                current = int(match.group(1))
                maximum = int(match.group(2))
                logger.info(f"✅ Парсинг: {current}/{maximum}")
                return (current, maximum)
            
            # Если нет формата с /, ищем просто числа
            numbers = re.findall(r'\d+', text)
            if len(numbers) >= 2:
                current = int(numbers[0])
                maximum = int(numbers[1])
                return (current, maximum)
            elif numbers:
                return (int(numbers[0]), 100)  # Предполагаем максимум 100
        
        logger.warning("❌ Не удалось найти информацию")
        return (None, None)
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return (None, None)

def create_progress_bar(current, maximum, length=15):
    """Создает красивый прогресс-бар"""
    if maximum <= 0:
        return "❌ Нет данных"
    
    filled = int((current / maximum) * length)
    filled = min(filled, length)  # На всякий случай
    
    bar = "🟩" * filled + "⬜" * (length - filled)
    percentage = (current / maximum) * 100
    
    return f"{bar} {percentage:.1f}%"

@tasks.loop(minutes=5)
async def update_status():
    """Автообновление статуса"""
    current, maximum = get_player_info()
    if current is not None and maximum is not None:
        status_text = f"🎮 {current}/{maximum}"
        await bot.change_presence(activity=discord.Game(name=status_text))
        logger.info(f"Статус обновлен: {status_text}")

@bot.event
async def on_ready():
    logger.info(f'✅ Бот {bot.user} запущен!')
    logger.info(f'ID бота: {bot.user.id}')
    logger.info(f'URL сайта: {TARGET_URL}')
    
    if AUTO_ROLE_ID:
        logger.info(f'✅ Авто-роль включена (ID: {AUTO_ROLE_ID})')
    
    update_status.start()

@bot.event
async def on_member_join(member):
    """Выдача роли новым участникам"""
    if not AUTO_ROLE_ID:
        return
    
    try:
        role = member.guild.get_role(AUTO_ROLE_ID)
        if role:
            await member.add_roles(role)
            logger.info(f'✅ Роль выдана {member.name}')
    except Exception as e:
        logger.error(f'❌ Ошибка выдачи роли: {e}')

@bot.command(name='players')
async def players(ctx):
    """Показать количество игроков (текущие / максимум)"""
    async with ctx.typing():
        current, maximum = get_player_info()
        
        if current is not None and maximum is not None:
            # Создаем прогресс-бар
            progress_bar = create_progress_bar(current, maximum)
            
            embed = discord.Embed(
                title="🎮 Онлайн на сервере",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            embed.add_field(
                name="👥 Игроки",
                value=f"**{current}/{maximum}**",
                inline=True
            )
            
            embed.add_field(
                name="📊 Заполненность",
                value=progress_bar,
                inline=False
            )
            
            # Добавляем цветовую индикацию
            if current >= maximum:
                color = "🔴 Сервер полон!"
            elif current >= maximum * 0.8:
                color = "🟡 Многолюдно"
            elif current >= maximum * 0.5:
                color = "🟢 Средне"
            else:
                color = "⚫ Мало людей"
            
            embed.add_field(name="Статус", value=color, inline=True)
            embed.set_footer(text=f"Запросил: {ctx.author.name}")
            
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ Ошибка",
                description="Не удалось получить информацию об онлайне",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

@bot.command(name='setrole')
@commands.has_permissions(administrator=True)
async def set_role(ctx, role: discord.Role):
    """Установка роли для новичков"""
    global AUTO_ROLE_ID
    AUTO_ROLE_ID = role.id
    
    embed = discord.Embed(
        title="✅ Роль настроена",
        description=f"Новые участники будут получать роль: {role.mention}",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='removerole')
@commands.has_permissions(administrator=True)
async def remove_role(ctx):
    """Отключение авто-выдачи роли"""
    global AUTO_ROLE_ID
    AUTO_ROLE_ID = 0
    
    embed = discord.Embed(
        title="🛑 Авто-выдача отключена",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

@bot.command(name='checkrole')
@commands.has_permissions(administrator=True)
async def check_role(ctx):
    """Проверка текущей роли"""
    if AUTO_ROLE_ID:
        role = ctx.guild.get_role(AUTO_ROLE_ID)
        if role:
            embed = discord.Embed(
                title="📋 Текущая роль",
                description=f"Выдается роль: {role.mention}",
                color=discord.Color.blue()
            )
        else:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Роль с ID {AUTO_ROLE_ID} не найдена",
                color=discord.Color.red()
            )
    else:
        embed = discord.Embed(
            title="ℹ️ Информация",
            description="Авто-выдача роли отключена",
            color=discord.Color.light_gray()
        )
    await ctx.send(embed=embed)

@bot.command(name='debug_players')
@commands.has_permissions(administrator=True)
async def debug_players(ctx):
    """Диагностика проблем"""
    try:
        await ctx.send("🔍 Проверяю API...")
        
        # Проверяем API
        api_url = "https://api.scpslgame.com/serverinfo.php?id=79795&players=true"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data and "Servers" in data and len(data["Servers"]) > 0:
                server = data["Servers"][0]
                players = server.get("Players", "не найдено")
                await ctx.send(f"✅ API: {players}")
            else:
                await ctx.send("❌ API не вернул данные")
        else:
            await ctx.send(f"❌ API ошибка: {response.status_code}")
        
        # Проверяем парсинг
        await ctx.send("\n🔍 Проверяю парсинг...")
        response = requests.get(TARGET_URL, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        element = soup.find('span', class_=['c-green', 'fw-b'])
        if element:
            await ctx.send(f"✅ Найдено: {element.text}")
        else:
            await ctx.send("❌ Элемент не найден")
            
    except Exception as e:
        await ctx.send(f"❌ Ошибка: {e}")

@bot.command(name='ping')
async def ping(ctx):
    """Проверка связи"""
    await ctx.send(f'🏓 Понг! {round(bot.latency * 1000)}мс')

@bot.command(name='help_custom')
async def help_custom(ctx):
    """Справка"""
    embed = discord.Embed(
        title="📚 Команды бота",
        description="Префикс: `!`",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="!players", value="Показать онлайн (текущие/максимум)", inline=False)
    embed.add_field(name="!ping", value="Проверка связи", inline=False)
    embed.add_field(name="!setrole @роль", value="Установить роль для новичков", inline=False)
    embed.add_field(name="!removerole", value="Отключить выдачу роли", inline=False)
    embed.add_field(name="!checkrole", value="Проверить текущую роль", inline=False)
    embed.add_field(name="!debug_players", value="Диагностика (админ)", inline=False)
    
    await ctx.send(embed=embed)

if __name__ == "__main__":
    if not TOKEN:
        logger.error("❌ Нет токена!")
        exit(1)
    bot.run(TOKEN)
