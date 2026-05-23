from flask import Flask
from threading import Thread

import discord
from discord.ext import commands
from discord.ext import tasks
from dotenv import load_dotenv

import os
import requests
from datetime import datetime, timezone

# =========================================
# KEEP RENDER ALIVE
# =========================================

app = Flask('')

@app.route('/')
def home():
    return "SyncSphere Bot is Running!"

@app.route('/ping')
def ping():
    return "pong"

def run_web():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# =========================================
# LOAD ENV
# =========================================

load_dotenv()

TOKEN      = os.getenv("TOKEN")
RENDER_URL = os.getenv("RENDER_URL")  # e.g. https://syncsphere-bot.onrender.com

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
# SELF-PING EVERY 4 MINUTES
# Render free tier sleeps after 50s idle.
# Pinging our own /ping endpoint keeps it
# awake 24/7 — no external service needed.
# =========================================

@tasks.loop(minutes=4)
async def self_ping():
    if not RENDER_URL:
        return
    try:
        url = RENDER_URL.rstrip("/") + "/ping"
        r = requests.get(url, timeout=10)
        now = datetime.now(timezone.utc).strftime("%H:%M UTC")
        print(f"[PING] {now} → {r.status_code}")
    except Exception as e:
        print(f"[PING ERROR] {e}")

# =========================================
# SCAN & ASSIGN MISSED MEMBERS
# Runs every 10 min — catches anyone who
# joined while the bot was briefly offline
# =========================================

@tasks.loop(minutes=10)
async def scan_missed_members():
    for guild in bot.guilds:
        missed = []
        for member in guild.members:
            if member.bot:
                continue
            existing = [r.name for r in member.roles]
            if not any(g in existing for g in GROUPS):
                missed.append(member)

        if missed:
            print(f"[SCAN] Found {len(missed)} unassigned member(s) in {guild.name} — assigning now")
            for member in missed:
                await assign_group(member)
        else:
            print(f"[SCAN] All members assigned in {guild.name}")

# =========================================
# GET COUNT FROM DISCORD
# Counts existing role assignments directly
# from Discord — survives any restart/sleep
# =========================================

def get_count_from_guild(guild):
    count = 0
    for group in GROUPS:
        role = discord.utils.get(guild.roles, name=group)
        if role:
            count += len(role.members)
    return count

# =========================================
# ASSIGN GROUP
# =========================================

async def assign_group(member):

    existing_roles = [role.name for role in member.roles]

    # Already assigned — skip
    if any(group in existing_roles for group in GROUPS):
        return

    # Always read count live from Discord — never from a file
    count = get_count_from_guild(member.guild)
    group = GROUPS[count % 4]

    role = discord.utils.get(member.guild.roles, name=group)

    if role:
        await member.add_roles(role)
    else:
        print(f"[ERROR] Role '{group}' not found in server — create it first!")
        return

    # DM the participant their group info
    try:
        await member.send(
            f"👋 Welcome to **Career Glow-up Night | GSA 2026**!\n\n"
            f"You have been assigned to:\n"
            f"✅ **{group}**\n\n"
            f"You can now see your private group channel in the server.\n\n"
            f"📋 **Prepare before your session:**\n"
            f"• Open **Gemini Chat**: gemini.google.com\n"
            f"• Open **Nano Banana** in another tab\n"
            f"• Keep your camera ready — it must be ON\n\n"
            f"Watch **#announcements** for your session date, time and Google Meet link.\n\n"
            f"Good luck — pitch yourself well! 🚀"
        )
    except discord.Forbidden:
        # User has DMs off — post in #welcome instead
        channel = discord.utils.get(member.guild.text_channels, name="welcome")
        if channel:
            await channel.send(
                f"{member.mention} you've been assigned to **{group}**! "
                f"Check your group channel. (Enable DMs to get session details!)"
            )

    print(f"[ASSIGNED] {member.name} → {group} (total assigned: {count + 1})")

# =========================================
# BOT READY
# =========================================

@bot.event
async def on_ready():
    print("=" * 50)
    print(f"Logged in as {bot.user}")
    print("SyncSphere is ONLINE")
    print("=" * 50)

    # Print current group counts on every startup
    for guild in bot.guilds:
        print(f"\n[GUILD] {guild.name}")
        for group in GROUPS:
            role = discord.utils.get(guild.roles, name=group)
            count = len(role.members) if role else 0
            print(f"  {group}: {count} members")

    # Start background tasks
    if not self_ping.is_running():
        self_ping.start()

    if not scan_missed_members.is_running():
        scan_missed_members.start()

    # Immediately scan for any missed members on startup
    await scan_missed_members()

# =========================================
# MEMBER JOIN — instant assignment
# =========================================

@bot.event
async def on_member_join(member):
    await assign_group(member)

# =========================================
# ON MESSAGE — backup for missed joins
# If someone joined during downtime and
# sends any message, they get assigned
# =========================================

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await assign_group(message.author)
    await bot.process_commands(message)

# =========================================
# MANUAL VERIFY — user types !verify
# =========================================

@bot.command()
async def verify(ctx):
    await assign_group(ctx.author)
    await ctx.send(f"{ctx.author.mention} verified!")

# =========================================
# ADMIN: !counts — see group breakdown
# =========================================

@bot.command()
@commands.has_permissions(manage_roles=True)
async def counts(ctx):
    lines = ["**Current group assignments:**\n"]
    total = 0
    for group in GROUPS:
        role = discord.utils.get(ctx.guild.roles, name=group)
        n = len(role.members) if role else 0
        total += n
        filled = "█" * n
        empty  = "░" * max(0, 45 - n)
        lines.append(f"**{group}**: {n} members\n`{filled}{empty}`")
    lines.append(f"\n**Total assigned:** {total}")
    await ctx.send("\n".join(lines))

# =========================================
# ADMIN: !sync — manually fix missed joins
# =========================================

@bot.command()
@commands.has_permissions(manage_roles=True)
async def sync(ctx):
    await ctx.send("Scanning for unassigned members...")
    fixed = 0
    for member in ctx.guild.members:
        if member.bot:
            continue
        existing = [r.name for r in member.roles]
        if not any(g in existing for g in GROUPS):
            await assign_group(member)
            fixed += 1
    await ctx.send(f"Done! Assigned **{fixed}** previously unassigned member(s).")

# =========================================
# START
# =========================================

keep_alive()
bot.run(TOKEN)
