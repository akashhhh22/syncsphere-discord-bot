import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import json

load_dotenv()

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

GROUPS = ["Group A", "Group B", "Group C", "Group D"]

FILE = "count.json"

# =========================
# COUNTER
# =========================

def get_count():

    if not os.path.exists(FILE):
        return 0

    try:
        with open(FILE, "r") as f:
            data = json.load(f)
            return data.get("count", 0)

    except:
        return 0


def save_count(count):

    with open(FILE, "w") as f:
        json.dump({"count": count}, f)


# =========================
# ASSIGN GROUP FUNCTION
# =========================

async def assign_group(member):

    existing_roles = [role.name for role in member.roles]

    # already assigned
    if any(group in existing_roles for group in GROUPS):
        return

    count = get_count()

    group = GROUPS[count % 4]

    role = discord.utils.get(member.guild.roles, name=group)

    if role:
        await member.add_roles(role)

    save_count(count + 1)

    try:
        await member.send(
            f"You were assigned to {group}"
        )
    except:
        pass

    print(f"{member.name} assigned to {group}")


# =========================
# READY
# =========================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


# =========================
# NORMAL JOIN EVENT
# =========================

@bot.event
async def on_member_join(member):

    await assign_group(member)


# =========================
# AUTO RECOVERY SYSTEM
# =========================

@bot.event
async def on_message(message):

    if message.author.bot:
        return

    member = message.author

    # if bot missed join because hosting slept
    await assign_group(member)

    await bot.process_commands(message)


bot.run(TOKEN)