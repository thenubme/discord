import os
import sys
import subprocess

# ============================================================================
# AUTO-ENVIRONMENT SETUP
# ============================================================================
# This section runs BEFORE other imports to ensure the virtual environment
# exists and dependencies are installed. On first run, it will:
# 1. Create a virtual environment in the script directory
# 2. Install required dependencies (aiohttp)
# 3. Re-launch itself inside the virtual environment
# ============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(SCRIPT_DIR, ".venv")

def is_in_venv():
    """Check if we're running inside a virtual environment"""
    return (hasattr(sys, 'real_prefix') or 
            (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))

def get_venv_python():
    """Get the path to the Python executable inside the venv"""
    if os.name == 'nt':  # Windows
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    else:  # Linux/Termux/Mac
        return os.path.join(VENV_DIR, "bin", "python")

def get_venv_pip():
    """Get the path to pip inside the venv"""
    if os.name == 'nt':  # Windows
        return os.path.join(VENV_DIR, "Scripts", "pip.exe")
    else:  # Linux/Termux/Mac
        return os.path.join(VENV_DIR, "bin", "pip")

def setup_environment():
    """Create venv and install dependencies if needed"""
    venv_python = get_venv_python()
    
    # Check if venv exists
    if not os.path.exists(venv_python):
        print("=" * 55)
        print("🔧 FIRST-TIME SETUP - Creating virtual environment...")
        print("=" * 55)
        
        try:
            # Create virtual environment
            print("📦 Creating venv...")
            subprocess.run([sys.executable, "-m", "venv", VENV_DIR], check=True)
            print("✅ Virtual environment created!")
            
            # Install dependencies
            print("📥 Installing aiohttp...")
            pip_path = get_venv_pip()
            subprocess.run([pip_path, "install", "--quiet", "aiohttp"], check=True)
            print("✅ Dependencies installed!")
            print("-" * 55)
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Setup failed: {e}")
            print("Please install manually:")
            print("  python -m venv .venv")
            print("  .venv\\Scripts\\pip install aiohttp  (Windows)")
            print("  .venv/bin/pip install aiohttp  (Linux/Termux)")
            sys.exit(1)
    
    # If we're not in the venv, re-launch inside it
    if not is_in_venv():
        print("🔄 Launching inside virtual environment...")
        # Pass all original arguments
        args = [venv_python] + sys.argv
        os.execv(venv_python, args)

# Run environment setup BEFORE importing other dependencies
setup_environment()

# ============================================================================
# Now safe to import dependencies that require installation
# ============================================================================
import asyncio
import aiohttp
import uuid
import time
import random
import signal
import json
from datetime import datetime, timedelta, timezone
from getpass import getpass

# ============================================================================
# TERMUX/ANDROID BATTERY OPTIMIZED SCHEDULER
# ============================================================================
# This version is designed for near-zero battery consumption:
# - Event-based scheduling (no polling loops)
# - Precise sleep calculations (CPU sleeps until exact action time)
# - Termux wake-lock integration (only acquires when needed)
# - Long sleep during training days (sleeps until next battle day)
# - Secure token storage (prompted on first run, saved to config file)
# - Auto virtual environment setup (no manual pip install needed)
# ============================================================================

# Config file path (stored in same directory as script)
CONFIG_FILE = os.path.join(SCRIPT_DIR, ".auth_config")

# User token - loaded from config file
USER_TOKEN = None

# CW2 STATS bot command details
NUDGE_COMMAND_ID = "1406484207269843017"
NUDGE_COMMAND_VERSION = "1406484207269843018"
BOT_APPLICATION_ID = "869761158763143218"

# Target configuration
TARGET_GUILD_ID = "952737615793254461"
TARGET_CHANNEL_ID = "1001637753840222269"

# Startup message channel
STARTUP_GUILD_ID = "1297294853448663050"
STARTUP_CHANNEL_ID = "1297294853935206512"

# All available tags
TAGS = ["feed", "tame", "edge", "hev", "city"]

# Termux detection
IS_TERMUX = os.path.exists('/data/data/com.termux')

def log(message, level="INFO"):
    """Battery-efficient logging with timestamps"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] [{level}] {message}")
    sys.stdout.flush()  # Ensure output is written immediately

def load_auth_token():
    """Load auth token from config file, or prompt user if not found"""
    global USER_TOKEN
    
    # Try to load from config file
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                USER_TOKEN = config.get('auth_token')
                if USER_TOKEN:
                    log("🔑 Auth token loaded from config", "AUTH")
                    return True
        except Exception as e:
            log(f"⚠️ Error reading config: {e}", "WARN")
    
    # Prompt user for token
    print("\n" + "=" * 55)
    print("🔐 FIRST-TIME SETUP - Authentication Required")
    print("=" * 55)
    print("Your auth token will be saved locally and won't be")
    print("stored in the script. You'll only need to enter this once.")
    print("-" * 55)
    
    try:
        # Use getpass for hidden input (won't show characters)
        USER_TOKEN = getpass("Enter your Discord auth token: ").strip()
        
        if not USER_TOKEN:
            log("❌ No token provided. Exiting.", "AUTH")
            sys.exit(1)
        
        # Save to config file
        save_auth_token(USER_TOKEN)
        log("✅ Auth token saved successfully!", "AUTH")
        print("-" * 55 + "\n")
        return True
        
    except KeyboardInterrupt:
        print("\n")
        log("❌ Setup cancelled by user", "AUTH")
        sys.exit(1)

def save_auth_token(token):
    """Save auth token to config file"""
    try:
        config = {'auth_token': token}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        
        # On Unix systems, restrict file permissions (owner read/write only)
        if not IS_TERMUX and os.name != 'nt':
            os.chmod(CONFIG_FILE, 0o600)
        
        return True
    except Exception as e:
        log(f"⚠️ Error saving config: {e}", "WARN")
        return False

def reset_auth_token():
    """Delete saved auth token (for re-authentication)"""
    if os.path.exists(CONFIG_FILE):
        try:
            os.remove(CONFIG_FILE)
            log("🗑️ Auth config deleted", "AUTH")
            return True
        except Exception as e:
            log(f"⚠️ Error deleting config: {e}", "WARN")
    return False

def acquire_wakelock():
    """Acquire Termux partial wake-lock to prevent CPU sleep during operations"""
    if IS_TERMUX:
        try:
            subprocess.run(['termux-wake-lock'], timeout=5, capture_output=True)
            log("🔒 Wake-lock acquired", "POWER")
            return True
        except Exception as e:
            log(f"⚠️ Wake-lock failed: {e}", "WARN")
    return False

def release_wakelock():
    """Release Termux wake-lock to allow CPU to sleep"""
    if IS_TERMUX:
        try:
            subprocess.run(['termux-wake-unlock'], timeout=5, capture_output=True)
            log("🔓 Wake-lock released", "POWER")
            return True
        except Exception as e:
            log(f"⚠️ Wake-unlock failed: {e}", "WARN")
    return False

def is_war_day_active():
    """Check if current time is during Clash Royale Battle Days (Thu-Mon at 15:30 IST transitions)"""
    now_utc = datetime.now(timezone.utc)
    now_ist = now_utc + timedelta(hours=5, minutes=30)  # Convert to IST
    current_weekday = now_utc.weekday()
    current_hour = now_utc.hour
    
    # Battle Days: Thursday 15:30 IST to Monday 15:30 IST
    # Each battle day transitions at 15:30 IST (10:00 UTC)
    # Thursday = 3, Friday = 4, Saturday = 5, Sunday = 6, Monday = 0
    
    # Battle Day 1: Thu 15:30 IST → Fri 15:30 IST
    if current_weekday == 3 and current_hour >= 10:
        return True, "Battle Day 1: Thursday"
    elif current_weekday == 4 and current_hour < 10:
        return True, "Battle Day 1: ends @ 15:30 IST"
    
    # Battle Day 2: Fri 15:30 IST → Sat 15:30 IST
    elif current_weekday == 4 and current_hour >= 10:
        return True, "Battle Day 2: Friday"
    elif current_weekday == 5 and current_hour < 10:
        return True, "Battle Day 2: ends @ 15:30 IST"
    
    # Battle Day 3: Sat 15:30 IST → Sun 15:30 IST
    elif current_weekday == 5 and current_hour >= 10:
        return True, "Battle Day 3: Saturday"
    elif current_weekday == 6 and current_hour < 10:
        return True, "Battle Day 3: ends @ 15:30 IST"
    
    # Battle Day 4: Sun 15:30 IST → Mon 15:30 IST
    elif current_weekday == 6 and current_hour >= 10:
        return True, "Battle Day 4: Sunday"
    elif current_weekday == 0 and current_hour < 10:
        return True, "Battle Day 4: ends @ 15:30 IST"
    
    # Training Days: Mon 15:30 IST → Thu 15:30 IST
    else:
        return False, f"Training Day ({now_ist.strftime('%A %H:%M')} IST)"

def get_current_interval_hours():
    """Get current nudge interval based on battle day phase"""
    now_utc = datetime.now(timezone.utc)
    
    # Calculate hours since 10:00 UTC today (or yesterday if before 10:00)
    if now_utc.hour >= 10:
        day_start = now_utc.replace(hour=10, minute=0, second=0, microsecond=0)
    else:
        day_start = (now_utc - timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    
    hours_elapsed = (now_utc - day_start).total_seconds() / 3600
    hours_in_cycle = hours_elapsed % 24
    
    if hours_in_cycle < 12:
        return 3, "early phase (every 3h)"
    elif hours_in_cycle < 18:
        return 2, "mid phase (every 2h)"
    else:
        return 1, "final phase (every 1h)"

def get_next_battle_day_start():
    """Calculate seconds until next Battle Day starts (Thursday 10:00 UTC)"""
    now_utc = datetime.now(timezone.utc)
    
    # Find next Thursday 10:00 UTC
    days_until_thursday = (3 - now_utc.weekday()) % 7
    if days_until_thursday == 0 and now_utc.hour >= 10:
        days_until_thursday = 7
    
    next_thursday = now_utc.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=days_until_thursday)
    
    seconds_until = (next_thursday - now_utc).total_seconds()
    return max(seconds_until, 60)  # Minimum 60 seconds

def get_next_phase_change():
    """Calculate seconds until next phase change (12h, 18h, or 24h mark)"""
    now_utc = datetime.now(timezone.utc)
    
    if now_utc.hour >= 10:
        day_start = now_utc.replace(hour=10, minute=0, second=0, microsecond=0)
    else:
        day_start = (now_utc - timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    
    hours_elapsed = (now_utc - day_start).total_seconds() / 3600
    hours_in_cycle = hours_elapsed % 24
    
    # Phase boundaries at 12h, 18h, 24h
    if hours_in_cycle < 12:
        next_boundary = 12
    elif hours_in_cycle < 18:
        next_boundary = 18
    else:
        next_boundary = 24
    
    seconds_until_phase = (next_boundary - hours_in_cycle) * 3600
    return max(seconds_until_phase, 60)

# Global variable to track last executed interval
_last_executed_interval = None

def get_current_interval_id():
    """
    Get a unique identifier for the current interval.
    Returns (interval_number, interval_hours) where interval_number changes each time we enter a new interval.
    """
    now_utc = datetime.now(timezone.utc)
    
    # Calculate day start (10:00 UTC)
    if now_utc.hour >= 10:
        day_start = now_utc.replace(hour=10, minute=0, second=0, microsecond=0)
    else:
        day_start = (now_utc - timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    
    hours_since_day_start = (now_utc - day_start).total_seconds() / 3600
    hours_in_cycle = hours_since_day_start % 24
    
    # Determine current phase and interval
    if hours_in_cycle < 12:  # Early phase: every 3 hours
        interval_hours = 3
        interval_num = int(hours_in_cycle // 3)
    elif hours_in_cycle < 18:  # Mid phase: every 2 hours
        interval_hours = 2
        interval_num = 4 + int((hours_in_cycle - 12) // 2)  # 4-6
    else:  # Final phase: every 1 hour
        interval_hours = 1
        interval_num = 7 + int((hours_in_cycle - 18) // 1)  # 7-12
    
    # Create unique interval ID (includes day to avoid cross-day confusion)
    day_id = day_start.strftime('%Y%m%d')
    interval_id = f"{day_id}_{interval_num}"
    
    return interval_id, interval_hours

def calculate_sleep_duration():
    """
    Calculate optimal sleep duration for battery efficiency.
    Returns (sleep_seconds, reason, should_execute_now)
    
    NEW LOGIC: Track which interval we've executed in. If we're in a new interval
    that we haven't executed yet, execute now. This is much more reliable than
    trying to hit a tiny 2-minute window.
    """
    global _last_executed_interval
    
    active, status = is_war_day_active()
    
    if not active:
        # Sleep until next Battle Day - maximum battery savings
        _last_executed_interval = None  # Reset on training days
        sleep_secs = get_next_battle_day_start()
        return sleep_secs, f"Training day - sleeping until next Battle Day", False
    
    # During Battle Days, check if we need to execute
    current_interval, interval_hours = get_current_interval_id()
    interval_seconds = interval_hours * 3600
    phase = f"{'early' if interval_hours == 3 else 'mid' if interval_hours == 2 else 'final'} phase (every {interval_hours}h)"
    
    # Check if we've already executed in this interval
    if _last_executed_interval != current_interval:
        # NEW INTERVAL - we should execute now!
        return 0, f"{phase} - Execute now (interval: {current_interval})", True
    
    # Already executed in this interval, calculate time until next interval
    now_utc = datetime.now(timezone.utc)
    
    if now_utc.hour >= 10:
        day_start = now_utc.replace(hour=10, minute=0, second=0, microsecond=0)
    else:
        day_start = (now_utc - timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    
    seconds_since_day_start = (now_utc - day_start).total_seconds()
    seconds_into_interval = seconds_since_day_start % interval_seconds
    seconds_until_next = interval_seconds - seconds_into_interval
    
    # Also check if phase will change before next interval
    phase_change_seconds = get_next_phase_change()
    
    # Use whichever comes first
    if phase_change_seconds < seconds_until_next:
        return phase_change_seconds, f"Phase change in {phase_change_seconds/3600:.1f}h", False
    
    return seconds_until_next, f"{phase} - Next action in {seconds_until_next/60:.0f}min", False

def mark_interval_executed():
    """Mark the current interval as executed"""
    global _last_executed_interval
    current_interval, _ = get_current_interval_id()
    _last_executed_interval = current_interval
    log(f"✅ Marked interval {current_interval} as executed", "SCHED")

async def send_startup_message():
    """Send startup notification"""
    headers = {
        "Authorization": USER_TOKEN,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://discord.com/api/v10/channels/{STARTUP_CHANNEL_ID}/messages"
            async with session.post(url, json={"content": "hi"}, headers=headers) as response:
                if response.status in [200, 204]:
                    log("👋 Startup message sent", "NET")
                else:
                    log(f"⚠️ Startup failed: {response.status}", "WARN")
    except Exception as e:
        log(f"⚠️ Startup error: {e}", "WARN")

async def send_nudge_interaction(session, tag_value, attempt_num, headers):
    """Send a single nudge command"""
    try:
        session_id = str(uuid.uuid4()).replace('-', '')
        nonce = str(int(datetime.now().timestamp() * 1000000))
        
        payload = {
            "type": 2,
            "application_id": BOT_APPLICATION_ID,
            "guild_id": TARGET_GUILD_ID,
            "channel_id": TARGET_CHANNEL_ID,
            "session_id": session_id,
            "data": {
                "version": NUDGE_COMMAND_VERSION,
                "id": NUDGE_COMMAND_ID,
                "name": "nudge",
                "type": 1,
                "options": [{"type": 3, "name": "tag", "value": tag_value}]
            },
            "nonce": nonce,
            "analytics_location": "slash_ui"
        }
        
        log(f"   🎯 Tag: {tag_value} (#{attempt_num})")
        
        async with session.post("https://discord.com/api/v10/interactions", 
                                json=payload, headers=headers) as response:
            if response.status in [200, 204]:
                log(f"   ✅ Success", "NET")
                return True
            else:
                log(f"   ❌ Failed: {response.status}", "WARN")
                return False
    except Exception as e:
        log(f"   ❌ Error: {e}", "WARN")
        return False

async def execute_nudge_sequence():
    """Execute all nudge commands - acquires wake-lock only during this operation"""
    log("🕐 Starting nudge sequence", "ACTION")
    
    # Acquire wake-lock only during network operations
    acquire_wakelock()
    
    headers = {
        "Authorization": USER_TOKEN,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
        "Accept": "*/*",
        "Origin": "https://discord.com"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            success_count = 0
            for i, tag in enumerate(TAGS):
                if await send_nudge_interaction(session, tag, i+1, headers):
                    success_count += 1
                # Short random delay between commands
                await asyncio.sleep(random.randint(5, 15))
            
            log(f"✅ Complete: {success_count}/{len(TAGS)} successful", "ACTION")
    finally:
        # Always release wake-lock after operations
        release_wakelock()

def battery_efficient_sleep(seconds):
    """
    Sleep in a battery-efficient way.
    Uses long sleeps that allow CPU to enter deep sleep.
    """
    if seconds <= 0:
        return
    
    log(f"💤 Sleeping for {seconds/60:.1f} minutes ({seconds/3600:.2f} hours)", "POWER")
    
    # For very long sleeps (> 1 hour), break into chunks for status updates
    max_chunk = 3600  # 1 hour max chunks
    
    remaining = seconds
    while remaining > 0:
        sleep_time = min(remaining, max_chunk)
        time.sleep(sleep_time)
        remaining -= sleep_time
        
        # Log status for long sleeps
        if remaining > 0:
            log(f"   ⏰ {remaining/3600:.1f}h remaining", "POWER")

def run_scheduler():
    """
    Main scheduler loop - EVENT-BASED for battery efficiency.
    
    Instead of polling every 30 seconds, this calculates the EXACT
    time until the next action is needed and sleeps precisely that long.
    This allows the Android CPU to enter deep sleep and consume ~0% battery.
    """
    log("🤖 Discord CW2 STATS Bot - BATTERY OPTIMIZED", "INIT")
    log("=" * 55, "INIT")
    log("📱 Termux Mode: " + ("ACTIVE" if IS_TERMUX else "Desktop"), "INIT")
    log("🔋 Battery Mode: Event-based (near-zero drain)", "INIT")
    log("📅 Battle Days: Thu 15:30 IST → Mon 15:30 IST", "INIT")
    log("⏰ Schedule: 3h (early) → 2h (mid) → 1h (final)", "INIT")
    log("=" * 55, "INIT")
    
    # Handle graceful shutdown
    def signal_handler(sig, frame):
        log("\n🛑 Shutting down gracefully...", "SYSTEM")
        release_wakelock()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        while True:
            # Calculate optimal sleep duration
            sleep_seconds, reason, execute_now = calculate_sleep_duration()
            
            active, status = is_war_day_active()
            log(f"📊 Status: {status}", "STATUS")
            log(f"📋 {reason}", "STATUS")
            
            if execute_now:
                # Time to execute - run nudge sequence
                asyncio.run(execute_nudge_sequence())
                
                # Mark this interval as executed (prevents re-execution)
                mark_interval_executed()
                
                # Recalculate sleep duration (will now show time until next interval)
                sleep_seconds, reason, _ = calculate_sleep_duration()
                log(f"📋 {reason}", "STATUS")
                
                if sleep_seconds > 0:
                    battery_efficient_sleep(sleep_seconds)
            else:
                # Not time yet - sleep until next action
                battery_efficient_sleep(sleep_seconds)
                
    except KeyboardInterrupt:
        log("\n🛑 Stopped by user", "SYSTEM")
        release_wakelock()

if __name__ == "__main__":
    log("Discord CW2 STATS Bot - Battery Optimized", "INIT")
    log("=" * 45, "INIT")
    
    # Check for --reset argument to re-authenticate
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        reset_auth_token()
        log("Run the script again to enter a new token", "AUTH")
        sys.exit(0)
    
    # Load or prompt for auth token (MUST be done first)
    load_auth_token()
    
    # Send startup message
    log("Sending startup message...", "INIT")
    asyncio.run(send_startup_message())
    
    # Start the event-based scheduler
    log("Starting battery-efficient scheduler...", "INIT")
    run_scheduler()
