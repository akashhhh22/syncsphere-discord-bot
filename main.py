from flask import Flask
from threading import Thread

import discord
from discord.ext import commands
from dotenv import load_dotenv

import os
import json

# =========================================
# KEEP RENDER ALIVE
# =========================================

app = Flask('')

@app.route('/')
def home():
    return "SyncSphere Bot is Running!"

def run_web():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# =========================================
# LOAD ENV
# =========================================

load_dotenv()

TOKEN = os.getenv("TOKEN")

# =========================================
# DISCORD INTENTS
# =========================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# =========================================
# BOT SETUP
# =========================================

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# =========================================
# GROUPS
# =========================================

GROUPS = [
    "Group A",
    "Group B",
    "Group C",
    "Group D"
]

# =========================================
# COUNTER FILE
# =========================================

FILE = "count.json"

# =========================================
# GET COUNT
# =========================================

def get_count():

    if not os.path.exists(FILE):
        return 0

    try:
        with open(FILE, "r") as f:
            data = json.load(f)
            return data.get("count", 0)

    except:
        return 0

# =========================================
# SAVE COUNT
# =========================================

def save_count(count):

    with open(FILE, "w") as f:
        json.dump({"count": count}, f)

# =========================================
# ASSIGN GROUP
# =========================================

async def assign_group(member):

    existing_roles = [role.name for role in member.roles]

    # already assigned
    if any(group in existing_roles for group in GROUPS):
        return

    count = get_count()

    group = GROUPS[count % 4]

    role = discord.utils.get(
        member.guild.roles,
        name=group
    )

    if role:
        await member.add_roles(role)

    save_count(count + 1)

    try:
        await member.send(
            f"""
Welcome to Career Glow-up Night!

You were assigned to:
{group}

You can now access your private group channel.

Good luck!
"""
        )

    except:
        pass

    print(f"{member.name} assigned to {group}")

# =========================================
# BOT READY
# =========================================

@bot.event
async def on_ready():

    print("=" * 50)
    print(f"Logged in as {bot.user}")
    print("SyncSphere is ONLINE")
    print("=" * 50)

# =========================================
# MEMBER JOIN
# =========================================

@bot.event
async def on_member_join(member):

    await assign_group(member)

# =========================================
# AUTO RECOVERY SYSTEM
# fixes missed joins if Render slept
# =========================================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    member = message.author

    await assign_group(member)

    await bot.process_commands(message)

# =========================================
# MANUAL VERIFY COMMAND
# =========================================

@bot.command()
async def verify(ctx):

    member = ctx.author

    await assign_group(member)

    await ctx.send(
        f"{member.mention} verification completed."
    )

# =========================================
# START
# =========================================

keep_alive()

bot.run(TOKEN)