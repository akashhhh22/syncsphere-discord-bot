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
RENDER_URL = os.getenv("RENDER_URL")

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
    intents=intents,
    help_command=None  # We use a custom !help
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
# STATE
# =========================================

pending_reset   = {}   # guild_id → bool
bot_paused      = {}   # guild_id → bool
bot_start_time  = datetime.now(timezone.utc)

# =========================================
# SELF-PING EVERY 4 MINUTES
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
# SCAN MISSED MEMBERS EVERY 10 MINUTES
# =========================================

@tasks.loop(minutes=10)
async def scan_missed_members():
    for guild in bot.guilds:
        if bot_paused.get(guild.id):
            continue
        missed = []
        for member in guild.members:
            if member.bot:
                continue
            existing = [r.name for r in member.roles]
            if not any(g in existing for g in GROUPS):
                missed.append(member)
        if missed:
            print(f"[SCAN] {len(missed)} unassigned in {guild.name} — fixing")
            for member in missed:
                await assign_group(member)
        else:
            print(f"[SCAN] All assigned in {guild.name}")

# =========================================
# GET COUNT FROM DISCORD
# =========================================

def get_count_from_guild(guild):
    count = 0
    for group in GROUPS:
        role = discord.utils.get(guild.roles, name=group)
        if role:
            count += len(role.members)
    return count

def get_group_counts(guild):
    result = {}
    for group in GROUPS:
        role = discord.utils.get(guild.roles, name=group)
        result[group] = len(role.members) if role else 0
    return result

# =========================================
# ASSIGN GROUP
# =========================================

async def assign_group(member):
    if bot_paused.get(member.guild.id):
        return

    existing_roles = [role.name for role in member.roles]
    if any(group in existing_roles for group in GROUPS):
        return

    count = get_count_from_guild(member.guild)
    group = GROUPS[count % 4]

    role = discord.utils.get(member.guild.roles, name=group)
    if role:
        await member.add_roles(role)
    else:
        print(f"[ERROR] Role '{group}' not found!")
        return

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
        channel = discord.utils.get(member.guild.text_channels, name="welcome")
        if channel:
            await channel.send(
                f"{member.mention} you've been assigned to **{group}**! "
                f"Check your group channel. (Enable DMs to get session details!)"
            )

    print(f"[ASSIGNED] {member.name} → {group} (total: {count + 1})")

# =========================================
# BOT READY
# =========================================

@bot.event
async def on_ready():
    print("=" * 50)
    print(f"Logged in as {bot.user}")
    print("SyncSphere is ONLINE")
    print("=" * 50)

    for guild in bot.guilds:
        print(f"\n[GUILD] {guild.name}")
        for group in GROUPS:
            role = discord.utils.get(guild.roles, name=group)
            count = len(role.members) if role else 0
            print(f"  {group}: {count} members")

    if not self_ping.is_running():
        self_ping.start()
    if not scan_missed_members.is_running():
        scan_missed_members.start()

    await scan_missed_members()

# =========================================
# MEMBER JOIN
# =========================================

@bot.event
async def on_member_join(member):
    await assign_group(member)

# =========================================
# ON MESSAGE — backup for missed joins
# =========================================

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await assign_group(message.author)
    await bot.process_commands(message)

# =========================================
# ==========================================
#              COMMANDS
# ==========================================
# =========================================

# ------------------------------------------
# !help — full command list
# ------------------------------------------

@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="SyncSphere Bot — Command Guide",
        description="All available commands for managing the GSA event.",
        color=0x5865F2
    )

    embed.add_field(
        name="👤 Member Commands",
        value=(
            "`!verify` — Get your group assigned if you were missed\n"
            "`!mygroup` — Check which group you are in\n"
            "`!status` — Check if the bot is running fine"
        ),
        inline=False
    )

    embed.add_field(
        name="📊 Admin — Info",
        value=(
            "`!counts` — See member count per group with bar chart\n"
            "`!listgroup <A/B/C/D>` — List all members in a group\n"
            "`!unassigned` — List members with no group role\n"
            "`!botinfo` — Uptime, ping, server stats"
        ),
        inline=False
    )

    embed.add_field(
        name="⚙️ Admin — Management",
        value=(
            "`!sync` — Assign all unassigned members\n"
            "`!assignmember @user <A/B/C/D>` — Manually assign a member\n"
            "`!removemember @user` — Remove a member's group role\n"
            "`!movemember @user <A/B/C/D>` — Move member to a different group\n"
            "`!pause` — Pause auto-assignment\n"
            "`!resume` — Resume auto-assignment"
        ),
        inline=False
    )

    embed.add_field(
        name="🔄 Admin — Reset",
        value=(
            "`!resetall` — Strip all roles and reassign everyone fresh\n"
            "`!confirmreset` — Confirm the reset\n"
            "`!cancelreset` — Cancel the reset"
        ),
        inline=False
    )

    embed.add_field(
        name="📢 Admin — Broadcast",
        value=(
            "`!announce <A/B/C/D> <message>` — DM all members of a group\n"
            "`!announceall <message>` — DM all assigned members"
        ),
        inline=False
    )

    embed.set_footer(text="Only commands marked Admin require Manage Roles permission.")
    await ctx.send(embed=embed)

# ------------------------------------------
# !verify — self-assign if missed
# ------------------------------------------

@bot.command()
async def verify(ctx):
    existing = [r.name for r in ctx.author.roles]
    if any(g in existing for g in GROUPS):
        group = next(g for g in GROUPS if g in existing)
        await ctx.send(f"{ctx.author.mention} you're already in **{group}**!")
        return
    await assign_group(ctx.author)
    await ctx.send(f"{ctx.author.mention} verified and assigned!")

# ------------------------------------------
# !mygroup — check your own group
# ------------------------------------------

@bot.command()
async def mygroup(ctx):
    existing = [r.name for r in ctx.author.roles]
    group = next((g for g in GROUPS if g in existing), None)
    if group:
        await ctx.send(f"{ctx.author.mention} you are in **{group}** ✅")
    else:
        await ctx.send(f"{ctx.author.mention} you haven't been assigned yet. Type `!verify` to get assigned.")

# ------------------------------------------
# !status — bot health check
# ------------------------------------------

@bot.command()
async def status(ctx):
    paused = bot_paused.get(ctx.guild.id, False)
    ping   = round(bot.latency * 1000)
    state  = "⏸️ Paused" if paused else "✅ Active"
    await ctx.send(
        f"**SyncSphere Status**\n"
        f"Bot: Online ✅\n"
        f"Auto-assign: {state}\n"
        f"Ping: {ping}ms\n"
        f"Self-ping: {'Running ✅' if self_ping.is_running() else 'Stopped ❌'}\n"
        f"Background scan: {'Running ✅' if scan_missed_members.is_running() else 'Stopped ❌'}"
    )

# ------------------------------------------
# !counts — group breakdown
# ------------------------------------------

@bot.command()
@commands.has_permissions(manage_roles=True)
async def counts(ctx):
    lines = ["**Current group assignments:**\n"]
    total = 0
    gc = get_group_counts(ctx.guild)
    for group, n in gc.items():
        total += n
        filled = "█" * n
        empty  = "░" * max(0, 45 - n)
        lines.append(f"**{group}**: {n} members\n`{filled}{empty}`")
    lines.append(f"\n**Total assigned:** {total}")
    await ctx.send("\n".join(lines))

# ------------------------------------------
# !listgroup <A/B/C/D> — list group members
# ------------------------------------------

@bot.command()
@commands.has_permissions(manage_roles=True)
async def listgroup(ctx, group_letter: str):
    group_name = f"Group {group_letter.upper()}"
    if group_name not in GROUPS:
        await ctx.send(f"Invalid group. Use A, B, C, or D.")
        return
    role = discord.utils.get(ctx.guild.roles, name=group_name)
    if not role or not role.members:
        await ctx.send(f"No members in **{group_name}** yet.")
        return
    names = "\n".join([f"{i+1}. {m.display_name}" for i, m in enumerate(role.members)])
    await ctx.send(f"**{group_name}** ({len(role.members)} members):\n{names}")

# ------------------------------------------
# !unassigned — who has no group yet
# ------------------------------------------

@bot.command()
@commands.has_permissions(manage_roles=True)
async def unassigned(ctx):
    missing = []
    for member in ctx.guild.members:
        if member.bot:
            continue
        existing = [r.name for r in member.roles]
        if not any(g in existing for g in GROUPS):
            missing.append(member.display_name)
    if not missing:
        await ctx.send("✅ Everyone has been assigned a group!")
        return
    names = "\n".join([f"{i+1}. {n}" for i, n in enumerate(missing)])
    await ctx.send(f"**Unassigned members ({len(missing)}):**\n{names}\n\nRun `!sync` to assign them all.")

# ------------------------------------------
# !botinfo — uptime and server stats
# ------------------------------------------

@bot.command()
@commands.has_permissions(manage_roles=True)
async def botinfo(ctx):
    now      = datetime.now(timezone.utc)
    uptime   = now - bot_start_time
    hours, r = divmod(int(uptime.total_seconds()), 3600)
    mins, _  = divmod(r, 60)
    ping     = round(bot.latency * 1000)
    total    = get_count_from_guild(ctx.guild)
    members  = sum(1 for m in ctx.guild.members if not m.bot)

    await ctx.send(
        f"**SyncSphere Bot Info**\n"
        f"Uptime: {hours}h {mins}m\n"
        f"Ping: {ping}ms\n"
        f"Server members: {members}\n"
        f"Assigned: {total}\n"
        f"Unassigned: {members - total}\n"
        f"Render URL: {RENDER_URL or 'Not set'}"
    )

# ------------------------------------------
# !sync — assign all unassigned members
# ------------------------------------------

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

# ------------------------------------------
# !assignmember @user <A/B/C/D>
# ------------------------------------------

@bot.command()
@commands.has_permissions(manage_roles=True)
async def assignmember(ctx, member: discord.Member, group_letter: str):
    group_name = f"Group {group_letter.upper()}"
    if group_name not in GROUPS:
        await ctx.send("Invalid group. Use A, B, C, or D.")
        return
    # Remove any existing group roles first
    existing_group_roles = [r for r in member.roles if r.name in GROUPS]
    if existing_group_roles:
        await member.remove_roles(*existing_group_roles)
    role = discord.utils.get(ctx.guild.roles, name=group_name)
    if not role:
        await ctx.send(f"Role **{group_name}** not found in server. Create it first.")
        return
    await member.add_roles(role)
    await ctx.send(f"✅ {member.mention} has been assigned to **{group_name}**.")

# ------------------------------------------
# !removemember @user
# ------------------------------------------

@bot.command()
@commands.has_permissions(manage_roles=True)
async def removemember(ctx, member: discord.Member):
    roles_to_remove = [r for r in member.roles if r.name in GROUPS]
    if not roles_to_remove:
        await ctx.send(f"{member.mention} has no group role to remove.")
        return
    await member.remove_roles(*roles_to_remove)
    await ctx.send(f"✅ Removed group role from {member.mention}.")

# ------------------------------------------
# !movemember @user <A/B/C/D>
# ------------------------------------------

@bot.command()
@commands.has_permissions(manage_roles=True)
async def movemember(ctx, member: discord.Member, group_letter: str):
    group_name = f"Group {group_letter.upper()}"
    if group_name not in GROUPS:
        await ctx.send("Invalid group. Use A, B, C, or D.")
        return
    old_roles = [r for r in member.roles if r.name in GROUPS]
    old_name  = old_roles[0].name if old_roles else "None"
    if old_roles:
        await member.remove_roles(*old_roles)
    role = discord.utils.get(ctx.guild.roles, name=group_name)
    if not role:
        await ctx.send(f"Role **{group_name}** not found. Create it first.")
        return
    await member.add_roles(role)
    await ctx.send(f"✅ Moved {member.mention} from **{old_name}** → **{group_name}**.")

# ------------------------------------------
# !pause — stop auto-assignment
# ------------------------------------------

@bot.command()
@commands.has_permissions(manage_roles=True)
async def pause(ctx):
    bot_paused[ctx.guild.id] = True
    await ctx.send("⏸️ Auto-assignment paused. New members will not be assigned until you run `!resume`.")

# ------------------------------------------
# !resume — restart auto-assignment
# ------------------------------------------

@bot.command()
@commands.has_permissions(manage_roles=True)
async def resume(ctx):
    bot_paused[ctx.guild.id] = False
    await ctx.send("▶️ Auto-assignment resumed. Run `!sync` to catch anyone who joined while paused.")

# ------------------------------------------
# !announce <A/B/C/D> <message>
# ------------------------------------------

@bot.command()
@commands.has_permissions(manage_roles=True)
async def announce(ctx, group_letter: str, *, message: str):
    group_name = f"Group {group_letter.upper()}"
    if group_name not in GROUPS:
        await ctx.send("Invalid group. Use A, B, C, or D.")
        return
    role = discord.utils.get(ctx.guild.roles, name=group_name)
    if not role or not role.members:
        await ctx.send(f"No members in **{group_name}**.")
        return
    sent = 0
    failed = 0
    await ctx.send(f"📢 Sending message to **{group_name}** ({len(role.members)} members)...")
    for member in role.members:
        try:
            await member.send(f"📢 **Message from your GSA Ambassador:**\n\n{message}")
            sent += 1
        except discord.Forbidden:
            failed += 1
    await ctx.send(f"✅ Sent to **{sent}** member(s). Failed (DMs off): **{failed}**.")

# ------------------------------------------
# !announceall <message>
# ------------------------------------------

@bot.command()
@commands.has_permissions(manage_roles=True)
async def announceall(ctx, *, message: str):
    sent = 0
    failed = 0
    targets = [m for m in ctx.guild.members if not m.bot and any(g in [r.name for r in m.roles] for g in GROUPS)]
    await ctx.send(f"📢 Sending to all **{len(targets)}** assigned members...")
    for member in targets:
        try:
            await member.send(f"📢 **Message from your GSA Ambassador:**\n\n{message}")
            sent += 1
        except discord.Forbidden:
            failed += 1
    await ctx.send(f"✅ Sent to **{sent}** member(s). Failed (DMs off): **{failed}**.")

# ------------------------------------------
# !resetall — full reset with confirmation
# ------------------------------------------

@bot.command()
@commands.has_permissions(manage_roles=True)
async def resetall(ctx):
    total = get_count_from_guild(ctx.guild)
    pending_reset[ctx.guild.id] = True
    await ctx.send(
        f"⚠️ **Are you sure?**\n"
        f"This will remove group roles from **{total}** member(s) and reassign everyone fresh.\n\n"
        f"Type `!confirmreset` to proceed or `!cancelreset` to abort."
    )

@bot.command()
@commands.has_permissions(manage_roles=True)
async def confirmreset(ctx):
    if not pending_reset.get(ctx.guild.id):
        await ctx.send("No reset pending. Run `!resetall` first.")
        return
    pending_reset[ctx.guild.id] = False
    await ctx.send("🔄 Resetting all group assignments...")

    stripped = 0
    for member in ctx.guild.members:
        if member.bot:
            continue
        roles_to_remove = [r for r in member.roles if r.name in GROUPS]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)
            stripped += 1

    await ctx.send(f"✅ Stripped **{stripped}** member(s). Reassigning now...")

    reassigned = 0
    for member in ctx.guild.members:
        if member.bot:
            continue
        await assign_group(member)
        reassigned += 1

    await ctx.send(
        f"✅ **Reset complete!**\n"
        f"**{reassigned}** member(s) reassigned.\n"
        f"Run `!counts` to see the new breakdown."
    )

@bot.command()
@commands.has_permissions(manage_roles=True)
async def cancelreset(ctx):
    pending_reset[ctx.guild.id] = False
    await ctx.send("❌ Reset cancelled. Nothing was changed.")

# =========================================
# START
# =========================================

keep_alive()
bot.run(TOKEN)
