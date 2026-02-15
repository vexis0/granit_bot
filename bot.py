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

# ID роли, которую нужно выдавать (нужно будет указать)
# ЗАМЕНИТЕ ЭТОТ ID НА ID ВАШЕЙ РОЛИ!
AUTO_ROLE_ID = int(os.getenv('AUTO_ROLE_ID', 0))  # Будет браться из переменных Railway

# Создание бота
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # ВКЛЮЧАЕМ ДОСТУП К УЧАСТНИКАМ (ОЧЕНЬ ВАЖНО!)
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

def get_player_count():
    """Получение количества игроков с сайта"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(TARGET_URL, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем элемент с игроками
        element = soup.find('span', class_=['c-green', 'fw-b'])
        
        if element:
            text = element.text
            logger.info(f"Найден текст: {text}")
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
    
    # Проверяем, настроена ли авто-роль
    if AUTO_ROLE_ID:
        logger.info(f'✅ Авто-выдача роли включена (ID роли: {AUTO_ROLE_ID})')
        
        # Проверяем доступность роли на всех серверах
        for guild in bot.guilds:
            role = guild.get_role(AUTO_ROLE_ID)
            if role:
                logger.info(f'На сервере "{guild.name}" найдена роль: {role.name}')
            else:
                logger.warning(f'На сервере "{guild.name}" роль с ID {AUTO_ROLE_ID} НЕ НАЙДЕНА!')
    else:
        logger.info('⚠️ Авто-выдача роли отключена (не указан ID роли)')
    
    update_status.start()

@bot.event
async def on_member_join(member):
    """
    Событие: новый участник зашел на сервер
    """
    logger.info(f'Новый участник: {member.name} на сервере {member.guild.name}')
    
    # Проверяем, включена ли авто-роль
    if not AUTO_ROLE_ID:
        return
    
    try:
        # Получаем роль по ID
        role = member.guild.get_role(AUTO_ROLE_ID)
        
        if role:
            # Выдаем роль новому участнику
            await member.add_roles(role)
            logger.info(f'✅ Роль "{role.name}" выдана {member.name}')
            
            # Отправляем приветственное сообщение (опционально)
            try:
                embed = discord.Embed(
                    title="👋 Добро пожаловать!",
                    description=f"Привет, {member.mention}! Ты получил роль **{role.name}**",
                    color=discord.Color.green()
                )
                # Отправляем в системный канал или первый доступный
                if member.guild.system_channel:
                    await member.guild.system_channel.send(embed=embed)
            except:
                pass  # Если не получилось отправить сообщение - игнорируем
        else:
            logger.error(f'❌ Роль с ID {AUTO_ROLE_ID} не найдена на сервере {member.guild.name}')
    except Exception as e:
        logger.error(f'❌ Ошибка при выдаче роли: {e}')

@bot.command(name='setrole')
@commands.has_permissions(administrator=True)
async def set_role(ctx, role: discord.Role):
    """
    Установка роли для автоматической выдачи
    Использование: !setrole @НазваниеРоли
    """
    global AUTO_ROLE_ID
    AUTO_ROLE_ID = role.id
    
    embed = discord.Embed(
        title="✅ Роль настроена",
        description=f"Теперь все новые участники будут получать роль: {role.mention}",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)
    
    # Советуем добавить в Railway
    await ctx.send("💡 **Совет**: Добавьте эту роль в переменные Railway, чтобы настройка сохранилась после перезапуска:\n"
                  f"`AUTO_ROLE_ID = {role.id}`")

@bot.command(name='removerole')
@commands.has_permissions(administrator=True)
async def remove_role(ctx):
    """
    Отключение автоматической выдачи роли
    """
    global AUTO_ROLE_ID
    AUTO_ROLE_ID = 0
    
    embed = discord.Embed(
        title="🛑 Авто-выдача отключена",
        description="Новые участники больше не будут получать роль автоматически",
        color=discord.Color.orange()
    )
    await ctx.send(embed=embed)

@bot.command(name='checkrole')
@commands.has_permissions(administrator=True)
async def check_role(ctx):
    """
    Проверка текущей роли
    """
    if AUTO_ROLE_ID:
        role = ctx.guild.get_role(AUTO_ROLE_ID)
        if role:
            embed = discord.Embed(
                title="📋 Текущая роль",
                description=f"Автоматически выдается роль: {role.mention}",
                color=discord.Color.blue()
            )
        else:
            embed = discord.Embed(
                title="❌ Ошибка",
                description=f"Роль с ID {AUTO_ROLE_ID} не найдена на этом сервере!\n"
                           "Возможно, роль была удалена.",
                color=discord.Color.red()
            )
    else:
        embed = discord.Embed(
            title="ℹ️ Информация",
            description="Автоматическая выдача роли **отключена**\n"
                       "Используйте `!setrole @роль` чтобы включить",
            color=discord.Color.light_gray()
        )
    await ctx.send(embed=embed)

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
    embed = discord.Embed(
        title="📚 Команды бота",
        description="Префикс: `!`",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="!players", value="Показать количество игроков онлайн", inline=False)
    embed.add_field(name="!ping", value="Проверка связи с ботом", inline=False)
    embed.add_field(name="!setrole @роль", value="(Админ) Установить роль для новичков", inline=False)
    embed.add_field(name="!removerole", value="(Админ) Отключить выдачу роли", inline=False)
    embed.add_field(name="!checkrole", value="(Админ) Проверить текущую роль", inline=False)
    embed.add_field(name="!test", value="(Админ) Тест парсера", inline=False)
    
    await ctx.send(embed=embed)

if __name__ == "__main__":
    if not TOKEN:
        logger.error("❌ Нет токена! Добавьте DISCORD_TOKEN в переменные окружения Railway")
        exit(1)
    bot.run(TOKEN)
