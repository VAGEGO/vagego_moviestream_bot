import os, asyncio, logging, sys, time
from aiohttp import web
from pyrogram import Client, filters, idle
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

# ── Logging ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("VageGo")

# ── Config ─────────────────────────────────────────────────────
API_ID       = os.environ.get("API_ID", "")
API_HASH     = os.environ.get("API_HASH", "")
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
OWNER_ID     = int(os.environ.get("OWNER_ID", "0"))
BASE_URL     = os.environ.get("BASE_URL", "").rstrip("/")
PORT         = int(os.environ.get("PORT", "8080"))
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "vagego2024")

# ── Validate ───────────────────────────────────────────────────
missing = [k for k,v in {"API_ID":API_ID,"API_HASH":API_HASH,"BOT_TOKEN":BOT_TOKEN}.items() if not v]
if missing:
    log.error(f"MISSING ENV VARS: {', '.join(missing)}")
    log.error("Go to: Render Dashboard → Your Service → Environment → Add Variables")
    sys.exit(1)

log.info(f"Config OK | PORT={PORT} | OWNER_ID={OWNER_ID} | BASE_URL={BASE_URL or 'NOT SET'}")

# ── File Store ─────────────────────────────────────────────────
FILE_STORE = {}

# ── Bot Client ─────────────────────────────────────────────────
bot = Client(
    name="vagego",
    api_id=int(API_ID),
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,   # No session file needed — works on Render free tier
)

# ── Helpers ────────────────────────────────────────────────────
def fmt_size(n):
    for u in ["B","KB","MB","GB"]:
        if n < 1024: return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"

def make_url(key):
    base = BASE_URL or f"http://localhost:{PORT}"
    return f"{base}/stream/{key}"

def is_owner(msg):
    if not OWNER_ID: return True
    return msg.from_user and msg.from_user.id == OWNER_ID

# ══════════════════════════════════════════════════════════════
# BOT COMMANDS
# ══════════════════════════════════════════════════════════════

@bot.on_message(filters.command("start") & filters.private)
async def cmd_start(_, msg: Message):
    name = msg.from_user.first_name if msg.from_user else "User"
    await msg.reply_text(
        f"👋 **Hello {name}!**\n\n"
        "🎬 **VageGo Stream Bot**\n\n"
        "আপনার চ্যানেল থেকে ভিডিও **forward** করুন।\n"
        "আমি একটি **permanent stream link** দেব।\n"
        "সেই link VageGo Admin Panel-এ paste করুন!\n\n"
        f"🌐 Server: `{BASE_URL or 'BASE_URL set করুন'}`\n"
        f"📁 Cached: `{len(FILE_STORE)}` files\n\n"
        "✅ Bot is Online!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🎬 VageGo App", url="https://vagego.netlify.app")
        ]])
    )

@bot.on_message(filters.command("ping") & filters.private)
async def cmd_ping(_, msg: Message):
    t = time.monotonic()
    m = await msg.reply_text("🏓 Pinging...")
    ms = round((time.monotonic() - t) * 1000)
    await m.edit_text(
        f"🏓 **Pong!** `{ms}ms`\n"
        f"✅ Bot: Online\n"
        f"✅ Server: Running\n"
        f"📁 Cached files: `{len(FILE_STORE)}`"
    )

@bot.on_message(filters.command("myid") & filters.private)
async def cmd_myid(_, msg: Message):
    await msg.reply_text(
        f"🆔 **Your Telegram ID:**\n`{msg.from_user.id}`\n\n"
        "এটি Render-এ `OWNER_ID` হিসেবে set করুন।"
    )

@bot.on_message(filters.command("stats") & filters.private)
async def cmd_stats(_, msg: Message):
    await msg.reply_text(
        f"📊 **Bot Stats**\n\n"
        f"📁 Cached files: `{len(FILE_STORE)}`\n"
        f"🌐 BASE_URL: `{BASE_URL or 'Not set'}`\n"
        f"🔌 Port: `{PORT}`\n"
        f"👤 Owner ID: `{OWNER_ID}`\n"
        f"✅ Status: Online"
    )

# ══════════════════════════════════════════════════════════════
# MAIN FEATURE — Video → Stream Link
# ══════════════════════════════════════════════════════════════

@bot.on_message(
    filters.private &
    (filters.video | filters.document | filters.audio | filters.animation)
)
async def on_media(_, msg: Message):
    # Only owner can use
    if not is_owner(msg):
        await msg.reply_text(
            f"🔒 এই bot শুধু owner ব্যবহার করতে পারবে।\n"
            f"আপনার ID: `{msg.from_user.id}`"
        )
        return

    proc = await msg.reply_text("⏳ Stream link তৈরি হচ্ছে...")

    try:
        media     = msg.video or msg.document or msg.audio or msg.animation
        file_id   = media.file_id
        file_name = getattr(media, "file_name", None) or f"video_{msg.id}.mp4"
        file_size = getattr(media, "file_size", 0) or 0
        mime_type = getattr(media, "mime_type", "video/mp4") or "video/mp4"

        if not mime_type.startswith(("video/", "audio/")):
            mime_type = "video/mp4"

        key = str(msg.id)
        FILE_STORE[key] = {
            "file_id"  : file_id,
            "file_name": file_name,
            "mime_type": mime_type,
            "file_size": file_size,
        }

        url = make_url(key)

        await proc.edit_text(
            f"✅ **Stream Link Ready!**\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📁 **File:** `{file_name}`\n"
            f"📦 **Size:** {fmt_size(file_size)}\n"
            f"🎞 **Type:** `{mime_type}`\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🔗 **Stream URL:**\n`{url}`\n\n"
            f"➡️ এই URL টি VageGo **Admin Panel**-এ paste করুন\n"
            f"♾️ এই link কখনো expire হবে না",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("▶ Browser-এ Test করুন", url=url)
            ]])
        )

        log.info(f"Stream link generated: {url} | {file_name} | {fmt_size(file_size)}")

    except FloodWait as e:
        await asyncio.sleep(e.value)
        await proc.edit_text(f"⚠️ Telegram rate limit। {e.value} সেকেন্ড পর আবার চেষ্টা করুন।")
    except Exception as e:
        log.error(f"on_media error: {e}", exc_info=True)
        await proc.edit_text(f"❌ Error: `{str(e)[:200]}`\n\nআবার চেষ্টা করুন।")


# ══════════════════════════════════════════════════════════════
# WEB SERVER
# ══════════════════════════════════════════════════════════════

async def handle_index(req):
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>VageGo Stream Server</title>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{font-family:'Segoe UI',sans-serif;background:#060d14;color:#e8f4fd;
         display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}}
    .card{{background:#0f1c2a;border:1px solid #1e3a52;border-radius:20px;
           padding:44px;text-align:center;max-width:460px;width:100%;
           box-shadow:0 20px 60px rgba(0,0,0,.5)}}
    h1{{font-size:40px;font-weight:900;letter-spacing:5px;margin-bottom:6px;
        background:linear-gradient(135deg,#1a6fad,#e87b1e);
        -webkit-background-clip:text;-webkit-text-fill-color:transparent}}
    .tag{{color:#7a9bb5;font-size:12px;letter-spacing:2px;margin-bottom:22px}}
    .badge{{display:inline-flex;align-items:center;gap:8px;
            background:rgba(46,204,113,.1);color:#2ecc71;
            border:1px solid rgba(46,204,113,.3);border-radius:30px;
            padding:9px 22px;font-weight:700;font-size:13px;margin-bottom:22px}}
    .dot{{width:9px;height:9px;background:#2ecc71;border-radius:50%;animation:p 1.4s infinite}}
    @keyframes p{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
    .info{{background:rgba(10,21,32,.7);border:1px solid #1e3a52;border-radius:12px;
           padding:18px 22px;text-align:left;margin-top:4px}}
    p{{color:#7a9bb5;font-size:13px;line-height:1.9;margin-bottom:6px}}
    p:last-child{{margin-bottom:0}}
    code{{background:#1e3a52;color:#f5a142;border-radius:4px;padding:2px 8px;
          font-family:monospace;font-size:12px}}
  </style>
</head>
<body>
  <div class="card">
    <h1>VAGEGO</h1>
    <div class="tag">TELEGRAM FILE STREAMING SERVER</div>
    <div class="badge"><div class="dot"></div> Server Online</div>
    <div class="info">
      <p>📁 Cached files: <code>{len(FILE_STORE)}</code></p>
      <p>🔗 Stream URL: <code>{BASE_URL}/stream/{{msg_id}}</code></p>
      <p>🤖 Bot: Send video → Get URL → Paste in Admin Panel</p>
    </div>
  </div>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")


async def handle_health(req):
    return web.json_response({
        "status" : "ok",
        "port"   : PORT,
        "base_url": BASE_URL,
        "cached" : len(FILE_STORE),
    })


async def handle_stream(req):
    key = req.match_info.get("message_id", "")

    if key not in FILE_STORE:
        return web.Response(
            text=f"File '{key}' not found.\nBot restart হলে এটা হয়। Video আবার forward করুন।",
            status=404, content_type="text/plain"
        )

    info      = FILE_STORE[key]
    file_id   = info["file_id"]
    file_name = info["file_name"]
    mime_type = info["mime_type"]
    file_size = info["file_size"]

    rh = req.headers.get("Range", "")
    start, end = 0, max(file_size - 1, 0)

    if rh and "=" in rh:
        try:
            p = rh.split("=", 1)[1].split("-", 1)
            start = int(p[0].strip()) if p[0].strip() else 0
            end   = int(p[1].strip()) if len(p) > 1 and p[1].strip() else max(file_size-1, 0)
        except Exception:
            pass

    cl = max(end - start + 1, 0)

    headers = {
        "Content-Type"               : mime_type,
        "Accept-Ranges"              : "bytes",
        "Content-Disposition"        : f'inline; filename="{file_name}"',
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
        "Access-Control-Allow-Headers": "Range, Content-Type",
    }
    if file_size > 0:
        headers["Content-Range"]  = f"bytes {start}-{end}/{file_size}"
        headers["Content-Length"] = str(cl)

    resp = web.StreamResponse(status=206 if rh else 200, headers=headers)
    try:
        await resp.prepare(req)
    except Exception:
        return resp

    try:
        sent = 0
        async for chunk in bot.stream_media(file_id, offset=start, limit=cl if cl > 0 else None):
            if not chunk: continue
            try:
                await resp.write(chunk)
            except Exception:
                break
            sent += len(chunk)
            if cl and sent >= cl: break
    except Exception as e:
        log.error(f"Stream error: {e}")

    try:
        await resp.write_eof()
    except Exception:
        pass

    return resp


async def handle_options(req):
    return web.Response(status=200, headers={
        "Access-Control-Allow-Origin" : "*",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
        "Access-Control-Allow-Headers": "Range, Content-Type",
    })


async def handle_cache(req):
    if req.query.get("secret", "") != ADMIN_SECRET:
        return web.Response(text="Unauthorized", status=401)
    return web.json_response({
        "count": len(FILE_STORE),
        "files": [
            {"id": k, "name": v["file_name"],
             "size": fmt_size(v["file_size"]), "url": make_url(k)}
            for k, v in FILE_STORE.items()
        ]
    })


# ══════════════════════════════════════════════════════════════
# STARTUP
# ══════════════════════════════════════════════════════════════

async def main():
    log.info("=" * 48)
    log.info("  VageGo Telegram Stream Bot")
    log.info("=" * 48)

    # 1. Start web server first (Render health check needs this)
    app = web.Application()
    app.router.add_get    ("/",                    handle_index)
    app.router.add_get    ("/health",              handle_health)
    app.router.add_get    ("/stream/{message_id}", handle_stream)
    app.router.add_options("/stream/{message_id}", handle_options)
    app.router.add_get    ("/cache",               handle_cache)

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    log.info(f"✅ Web server: http://0.0.0.0:{PORT}")
    log.info(f"🌐 Public URL: {BASE_URL or '⚠️  BASE_URL not set!'}")

    # 2. Start Telegram bot
    try:
        await bot.start()
        me = await bot.get_me()
        log.info(f"✅ Bot started: @{me.username} (ID: {me.id})")
        log.info(f"👤 Owner ID  : {OWNER_ID}")
        log.info("=" * 48)
        log.info("🚀 LIVE! Send /start to your bot on Telegram.")
        log.info("=" * 48)
    except Exception as e:
        log.error(f"❌ Bot failed to start: {e}")
        log.error("➡  Check API_ID, API_HASH, BOT_TOKEN in Render Environment")
        await asyncio.Event().wait()
        return

    await idle()
    await bot.stop()
    await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
