import os
import sys
import xml.etree.ElementTree as ET
from typing import Tuple, Optional
import dotenv
import mss
import mss.tools
import pygetwindow as gw
import requests
from PIL import Image

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# Load secrets from .env
dotenv.load_dotenv()


async def check_auth(update: Update) -> bool:
    """Verifies that the incoming update is from ALLOWED_TELEGRAM_USER_ID."""
    allowed_user = os.getenv("ALLOWED_TELEGRAM_USER_ID", "").strip()
    if not allowed_user:
        if update.effective_message:
            await update.effective_message.reply_text("⚠️ ALLOWED_TELEGRAM_USER_ID is not configured in .env.")
        return False
    user_id = str(update.effective_user.id) if update.effective_user else ""
    if user_id != allowed_user:
        # Ignore unauthorized users
        return False
    return True


# =====================================================================
# 1. SCREENSHOT & GEMINI ANALYSIS COMMANDS
# =====================================================================

def capture_window_screenshot(target_title: str) -> Tuple[Optional[str], Optional[str]]:
    """Finds target window, restores if minimized, screenshots via mss."""
    windows = gw.getWindowsWithTitle(target_title)
    if not windows:
        return None, f"No window matching '{target_title}' was found."

    win = windows[0]
    if win.isMinimized:
        try:
            win.restore()
        except Exception:
            pass

    bbox = {
        "top": max(0, win.top),
        "left": max(0, win.left),
        "width": max(10, win.width),
        "height": max(10, win.height),
    }

    with mss.mss() as sct:
        screenshot = sct.grab(bbox)
        temp_path = "temp_window.png"
        mss.tools.to_png(screenshot.rgb, screenshot.size, output=temp_path)
        return temp_path, None


def capture_full_screenshot() -> str:
    """Screenshots primary monitor via mss."""
    with mss.mss() as sct:
        monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
        screenshot = sct.grab(monitor)
        temp_path = "temp_full.png"
        mss.tools.to_png(screenshot.rgb, screenshot.size, output=temp_path)
        return temp_path


def analyze_image_with_gemini(image_path: str, prompt: str) -> str:
    """Sends screenshot image to Gemini API for text description."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return "Error: GEMINI_API_KEY is not configured in .env file."
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        img = Image.open(image_path)
        response = model.generate_content([prompt, img])
        return response.text.strip() if response.text else "No description generated."
    except Exception as e:
        return f"Error contacting Gemini API: {str(e)}"


async def describe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Screenshots specific target application window and describes it."""
    if not await check_auth(update):
        return
    target_title = os.getenv("TARGET_WINDOW_TITLE", "").strip()
    if not target_title:
        await update.message.reply_text("⚠️ TARGET_WINDOW_TITLE is not configured in .env.")
        return

    await update.message.reply_text(f"🔍 Capturing window containing '{target_title}'...")
    img_path, err = capture_window_screenshot(target_title)
    if err:
        await update.message.reply_text(err)
        return

    desc = analyze_image_with_gemini(img_path, "Briefly describe what is currently visible on this application window.")
    await update.message.reply_text(desc)
    if os.path.exists(img_path):
        os.remove(img_path)


async def describe_full_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Screenshots full primary screen and describes it."""
    if not await check_auth(update):
        return
    await update.message.reply_text("🖥️ Capturing full primary screen...")
    img_path = capture_full_screenshot()
    desc = analyze_image_with_gemini(img_path, "Briefly describe what is currently visible on this desktop screen.")
    await update.message.reply_text(desc)
    if os.path.exists(img_path):
        os.remove(img_path)


# =====================================================================
# 2. STUDY SESSION TIMER COMMANDS
# =====================================================================

def cancel_existing_jobs(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> bool:
    """Cancels any running timer or pomodoro jobs for the given chat_id."""
    current_jobs = context.job_queue.get_jobs_by_name(str(chat_id))
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True


async def timer_callback(context: ContextTypes.DEFAULT_TYPE):
    """Callback triggered when standard /timer fires."""
    job = context.job
    await context.bot.send_message(chat_id=job.chat_id, text="Time's up")


async def timer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Schedules a one-off reminder timer in minutes."""
    if not await check_auth(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /timer <minutes> (e.g., /timer 15)")
        return
    try:
        minutes = float(context.args[0])
        if minutes <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please specify a valid positive number of minutes.")
        return

    chat_id = update.effective_chat.id
    cancel_existing_jobs(context, chat_id)

    delay_seconds = minutes * 60.0
    context.job_queue.run_once(
        timer_callback,
        due=delay_seconds,
        chat_id=chat_id,
        name=str(chat_id),
        data={"type": "timer"},
    )
    await update.message.reply_text(f"⏱️ Timer set for {minutes} minute(s).")


async def pomodoro_callback(context: ContextTypes.DEFAULT_TYPE):
    """Callback handling alternating work and break phases in Pomodoro chain."""
    job = context.job
    data = job.data
    chat_id = job.chat_id

    work_min = data["work_min"]
    break_min = data["break_min"]
    total_cycles = data["total_cycles"]
    current_cycle = data["current_cycle"]
    phase = data["phase"]

    if phase == "work":
        if current_cycle < total_cycles:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Study block done, {break_min} min break"
            )
            next_data = {
                "type": "pomodoro",
                "work_min": work_min,
                "break_min": break_min,
                "total_cycles": total_cycles,
                "current_cycle": current_cycle,
                "phase": "break",
            }
            context.job_queue.run_once(
                pomodoro_callback,
                due=break_min * 60.0,
                chat_id=chat_id,
                name=str(chat_id),
                data=next_data,
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Study block done! All {total_cycles} pomodoro cycles completed!"
            )
    elif phase == "break":
        next_cycle = current_cycle + 1
        await context.bot.send_message(
            chat_id=chat_id,
            text="Break's over, back to it"
        )
        next_data = {
            "type": "pomodoro",
            "work_min": work_min,
            "break_min": break_min,
            "total_cycles": total_cycles,
            "current_cycle": next_cycle,
            "phase": "work",
        }
        context.job_queue.run_once(
            pomodoro_callback,
            due=work_min * 60.0,
            chat_id=chat_id,
            name=str(chat_id),
            data=next_data,
        )


async def pomodoro_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts alternating work/break Pomodoro cycles."""
    if not await check_auth(update):
        return
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: /pomodoro <work_minutes> <break_minutes> <cycles>\nExample: /pomodoro 25 5 4"
        )
        return
    try:
        work_min = float(context.args[0])
        break_min = float(context.args[1])
        cycles = int(context.args[2])
        if work_min <= 0 or break_min <= 0 or cycles <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "Please specify valid positive numbers: /pomodoro <work_minutes> <break_minutes> <cycles>"
        )
        return

    chat_id = update.effective_chat.id
    cancel_existing_jobs(context, chat_id)

    data = {
        "type": "pomodoro",
        "work_min": work_min,
        "break_min": break_min,
        "total_cycles": cycles,
        "current_cycle": 1,
        "phase": "work",
    }
    context.job_queue.run_once(
        pomodoro_callback,
        due=work_min * 60.0,
        chat_id=chat_id,
        name=str(chat_id),
        data=data,
    )
    await update.message.reply_text(
        f"🍅 Pomodoro started! Cycle 1/{cycles}: {work_min} min work block starting now."
    )


async def timer_cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancels any running timer or pomodoro for the chat."""
    if not await check_auth(update):
        return
    chat_id = update.effective_chat.id
    canceled = cancel_existing_jobs(context, chat_id)
    if canceled:
        await update.message.reply_text("🚫 Active timer / pomodoro canceled.")
    else:
        await update.message.reply_text("No active timer found.")


# =====================================================================
# 3. VLC PLAYBACK CONTROL COMMANDS
# =====================================================================

def send_vlc_command(command: str, extra_params: dict = None) -> Tuple[bool, str, Optional[ET.Element]]:
    """Helper hitting VLC's HTTP status/command API with Basic Auth."""
    host = os.getenv("VLC_HOST", "localhost").strip() or "localhost"
    port = os.getenv("VLC_PORT", "8080").strip() or "8080"
    password = os.getenv("VLC_HTTP_PASSWORD", "").strip()

    url = f"http://{host}:{port}/requests/status.xml"
    params = {}
    if command:
        params["command"] = command
    if extra_params:
        params.update(extra_params)

    try:
        resp = requests.get(url, params=params, auth=("", password), timeout=4)
        if resp.status_code == 401:
            return False, "⚠️ VLC HTTP authentication failed. Please check VLC_HTTP_PASSWORD in .env.", None
        if resp.status_code != 200:
            return False, f"⚠️ VLC HTTP returned status code {resp.status_code}.", None

        root = ET.fromstring(resp.text)
        return True, "OK", root
    except requests.RequestException:
        return False, f"⚠️ Could not connect to VLC HTTP interface at http://{host}:{port}. Make sure VLC is running with web interface enabled.", None
    except ET.ParseError:
        return False, "⚠️ Invalid response received from VLC HTTP interface.", None


async def vlc_play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggers VLC play command."""
    if not await check_auth(update):
        return
    success, msg, _ = send_vlc_command("pl_play")
    if success:
        await update.message.reply_text("▶️ VLC: Play command sent.")
    else:
        await update.message.reply_text(msg)


async def vlc_pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggers VLC pause command."""
    if not await check_auth(update):
        return
    success, msg, _ = send_vlc_command("pl_pause")
    if success:
        await update.message.reply_text("⏸️ VLC: Pause command sent.")
    else:
        await update.message.reply_text(msg)


async def vlc_next_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggers VLC next track command."""
    if not await check_auth(update):
        return
    success, msg, _ = send_vlc_command("pl_next")
    if success:
        await update.message.reply_text("⏭️ VLC: Next track command sent.")
    else:
        await update.message.reply_text(msg)


async def vlc_prev_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Triggers VLC previous track command."""
    if not await check_auth(update):
        return
    success, msg, _ = send_vlc_command("pl_previous")
    if success:
        await update.message.reply_text("⏮️ VLC: Previous track command sent.")
    else:
        await update.message.reply_text(msg)


async def vlc_volume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sets VLC volume level from 0 to 100%."""
    if not await check_auth(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /vlc_volume <0-100> (e.g., /vlc_volume 80)")
        return
    try:
        vol = int(context.args[0])
        if vol < 0 or vol > 100:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Please specify a volume percentage between 0 and 100.")
        return

    # In VLC HTTP API status.xml: val ranges 0 to 512 (where 256 is 100% standard volume)
    vlc_val = int(vol * 512 / 100)
    success, msg, _ = send_vlc_command("volume", {"val": str(vlc_val)})
    if success:
        await update.message.reply_text(f"🔊 VLC: Volume set to {vol}%.")
    else:
        await update.message.reply_text(msg)


async def vlc_now_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Queries VLC status.xml and replies with current playing track info or Nothing playing."""
    if not await check_auth(update):
        return
    success, msg, root = send_vlc_command("")
    if not success:
        await update.message.reply_text(msg)
        return

    state_elem = root.find("state")
    state = state_elem.text.strip().lower() if (state_elem is not None and state_elem.text) else "stopped"

    if state in ("stopped", "stop"):
        await update.message.reply_text("Nothing playing")
        return

    title, artist, filename = "", "", ""
    for category in root.findall(".//category"):
        if category.get("name") == "meta":
            for info in category.findall("info"):
                name = info.get("name")
                if name == "title":
                    title = info.text or ""
                elif name == "artist":
                    artist = info.text or ""
                elif name == "filename":
                    filename = info.text or ""

    track_name = title or filename
    if not track_name:
        await update.message.reply_text("Nothing playing")
        return

    if artist:
        await update.message.reply_text(f"🎵 {artist} - {track_name}")
    else:
        await update.message.reply_text(f"🎵 {track_name}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends list of available commands and usage instructions."""
    if not await check_auth(update):
        return
    help_text = (
        "🤖 *Bridge Bot Commands*\n\n"
        "📷 *Screen Description*\n"
        "/describe - Screenshot & describe target window\n"
        "/describe_full - Screenshot & describe primary screen\n\n"
        "⏱️ *Study Session Timer*\n"
        "/timer <minutes> - Set a reminder timer\n"
        "/pomodoro <work_min> <break_min> <cycles> - Start Pomodoro cycle chain\n"
        "/timer_cancel - Cancel running timer or pomodoro\n\n"
        "🎵 *VLC Playback Control*\n"
        "/vlc_play - Play media\n"
        "/vlc_pause - Pause media\n"
        "/vlc_next - Next track\n"
        "/vlc_prev - Previous track\n"
        "/vlc_volume <0-100> - Set volume percentage\n"
        "/vlc_now - Show currently playing track\n"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN is not set in .env file.")
        sys.exit(1)

    app = ApplicationBuilder().token(token).build()

    # Register Command Handlers
    app.add_handler(CommandHandler(["start", "help"], help_command))

    # 1. Screen Analysis
    app.add_handler(CommandHandler("describe", describe_command))
    app.add_handler(CommandHandler("describe_full", describe_full_command))

    # 2. Study Session Timer
    app.add_handler(CommandHandler("timer", timer_command))
    app.add_handler(CommandHandler("pomodoro", pomodoro_command))
    app.add_handler(CommandHandler("timer_cancel", timer_cancel_command))

    # 3. VLC Playback Control
    app.add_handler(CommandHandler("vlc_play", vlc_play_command))
    app.add_handler(CommandHandler("vlc_pause", vlc_pause_command))
    app.add_handler(CommandHandler("vlc_next", vlc_next_command))
    app.add_handler(CommandHandler("vlc_prev", vlc_prev_command))
    app.add_handler(CommandHandler("vlc_volume", vlc_volume_command))
    app.add_handler(CommandHandler("vlc_now", vlc_now_command))

    print("Bridge Bot service is active and listening for Telegram commands...")
    app.run_polling()


if __name__ == "__main__":
    main()
