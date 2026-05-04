import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'VageGo Bot is alive!')
    def log_message(self, *args):
        pass

threading.Thread(
    target=lambda: HTTPServer(('0.0.0.0', 8080), Handler).serve_forever(),
    daemon=True
).start()
import os, asyncio, logging, sys, time, json
from pathlib import Path
from aiohttp import web
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
    format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("VageGo")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID  = int(os.environ.get("OWNER_ID", "0"))
BASE_URL  = os.environ.get("BASE_URL", "").rstrip("/")
PORT      = int(os.environ.get("PORT", "8080"))

if not BOT_TOKEN:
    log.error("BOT_TOKEN missing!")
    sys.exit(1)

STORE_PATH = Path("/tmp/file_store.json")

def load_store():
    try:
        if STORE_PATH.exists():
            return json.loads(STORE_PATH.read_text())
    except Exception as e:
        log.warning(f"Store load error: {e}")
    return {}

def save_store(store):
    try:
        STORE_PATH.write_text(json.dumps(store, ensure_ascii=False))
    except Exception as e:
        log.warning(f"Store save error: {e}")

FILE_STORE = load_store()
log.info(f"Loaded {len(FILE_STORE)} cached files")

def make_url(key):
    return f"{BASE_URL or f'http://localhost:{PORT}'}/stream/{key}"

def fmt_size(n):
    for u in ["B","KB","MB","GB"]:
        if n < 1024: return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"

def is_owner(user_id):
    if not OWNER_ID: return True
    return user_id == OWNER_ID

# ══ COMMANDS ══════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "User"
    await update.message.reply_text(
        f"👋 **Hello {name}!**\n\n"
        "🎬 **VageGo Stream Bot**\n\n"
        "✅ যেকোনো **video forward** করুন\n"
        "🔗 সাথে সাথে **Stream Link** পাবেন!\n\n"
        f"📁 Cached: `{len(FILE_STORE)}` files",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🎬 VageGo App", url="https://vagego.netlify.app")
        ]])
    )

async def cmd_ping(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = time.monotonic()
    m = await update.message.reply_text("🏓 Pinging...")
    ms = round((time.monotonic() - t) * 1000)
    await m.edit_text(f"🏓 **Pong!** `{ms}ms`\n✅ Bot Online\n📁 Cached: `{len(FILE_STORE)}`", parse_mode="Markdown")

async def cmd_myid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🆔 Your ID: `{update.effective_user.id}`", parse_mode="Markdown"
    )

async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id): return
    if not FILE_STORE:
        await update.message.reply_text("📭 কোনো cached file নেই।")
        return
    lines = [f"📁 **Cached ({len(FILE_STORE)}):**\n"]
    for i, (k, v) in enumerate(list(FILE_STORE.items())[-10:], 1):
        lines.append(f"{i}. `{v['file_name']}`\n`{make_url(k)}`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

# ══ MAIN FEATURE ══════════════════════════════════

async def on_media(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    log.info(f"Media received from user: {user_id}")

    if not is_owner(user_id):
        await update.message.reply_text(
            f"🔒 শুধু owner ব্যবহার করতে পারবে।\nআপনার ID: `{user_id}`",
            parse_mode="Markdown"
        )
        return

    proc = await update.message.reply_text("⏳ Stream link তৈরি হচ্ছে...")

    try:
        msg = update.message
        media = msg.video or msg.document or msg.audio or msg.animation

        if not media:
            await proc.edit_text("❌ কোনো media পাওয়া যায়নি।")
            return

        file_id   = media.file_id
        file_name = getattr(media, "file_name", None) or f"video_{msg.message_id}.mp4"
        file_size = getattr(media, "file_size", 0) or 0
        mime_type = getattr(media, "mime_type", "video/mp4") or "video/mp4"

        if not mime_type.startswith(("video/", "audio/")):
            mime_type = "video/mp4"

        key = str(msg.message_id)
        FILE_STORE[key] = {
            "file_id": file_id,
            "file_name": file_name,
            "mime_type": mime_type,
            "file_size": file_size,
        }
        save_store(FILE_STORE)
        url = make_url(key)

        log.info(f"Stream link ready: {url} | {file_name}")

        await proc.edit_text(
            f"✅ **Stream Link Ready!**\n\n"
            f"📁 **File:** `{file_name}`\n"
            f"📦 **Size:** {fmt_size(file_size)}\n\n"
            f"🔗 **Stream URL:**\n`{url}`\n\n"
            f"➡️ এই URL VageGo Admin Panel এ paste করুন",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("▶ Test করুন", url=url)
            ]])
        )

    except Exception as e:
        log.error(f"on_media error: {e}", exc_info=True)
        await proc.edit_text(f"❌ Error: `{str(e)[:300]}`", parse_mode="Markdown")

# ══ WEB SERVER ════════════════════════════════════

async def handle_index(req):
    return web.Response(text=f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>VageGo Stream</title>
<style>body{{background:#060d14;color:#e8f4fd;font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}}
.c{{background:#0f1c2a;border:1px solid #1e3a52;border-radius:16px;padding:40px;text-align:center;max-width:400px}}
h1{{font-size:36px;font-weight:900;letter-spacing:4px;background:linear-gradient(135deg,#1a6fad,#e87b1e);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.b{{display:inline-flex;align-items:center;gap:8px;background:rgba(46,204,113,.1);color:#2ecc71;border:1px solid rgba(46,204,113,.3);border-radius:30px;padding:8px 20px;font-size:13px;margin:16px 0}}
.dot{{width:8px;height:8px;background:#2ecc71;border-radius:50%;animation:p 1.4s infinite}}@keyframes p{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
p{{color:#7a9bb5;font-size:13px}}code{{background:#1e3a52;color:#f5a142;border-radius:4px;padding:2px 6px}}</style></head>
<body><div class="c"><h1>VAGEGO</h1>
<div class="b"><div class="dot"></div> Server Online</div>
<p>📁 Cached: <code>{len(FILE_STORE)}</code> files</p>
<p>🤖 Video পাঠান → Link পান → App এ paste করুন</p></div></body></html>""",
    content_type="text/html")

async def handle_health(req):
    return web.json_response({"status":"ok","cached":len(FILE_STORE)})

async def handle_stream(req):
    key = req.match_info.get("message_id","")
    if key not in FILE_STORE:
        FILE_STORE.update(load_store())
    if key not in FILE_STORE:
        return web.Response(text=f"File '{key}' not found.", status=404)

    info = FILE_STORE[key]
    file_id   = info["file_id"]
    file_name = info["file_name"]
    mime_type = info["mime_type"]
    file_size = info["file_size"]

    # Download from Telegram and stream
    bot = req.app["bot"]
    try:
        tg_file = await bot.get_file(file_id)
        file_url = tg_file.file_path

        import aiohttp as aio
        rh = req.headers.get("Range","")
        headers = {
            "Content-Type": mime_type,
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{file_name}"',
            "Access-Control-Allow-Origin": "*",
        }

        async with aio.ClientSession() as session:
            req_headers = {}
            if rh: req_headers["Range"] = rh

            async with session.get(file_url, headers=req_headers) as r:
                if file_size > 0 and rh:
                    cr = r.headers.get("Content-Range","")
                    cl = r.headers.get("Content-Length","")
                    if cr: headers["Content-Range"] = cr
                    if cl: headers["Content-Length"] = cl

                resp = web.StreamResponse(status=r.status, headers=headers)
                await resp.prepare(req)
                async for chunk in r.content.iter_chunked(65536):
                    await resp.write(chunk)
                await resp.write_eof()
                return resp

    except Exception as e:
        log.error(f"Stream error: {e}")
        return web.Response(text=f"Stream error: {e}", status=500)

async def handle_options(req):
    return web.Response(status=200, headers={
        "Access-Control-Allow-Origin":"*",
        "Access-Control-Allow-Methods":"GET, HEAD, OPTIONS",
        "Access-Control-Allow-Headers":"Range, Content-Type",
    })

# ══ STARTUP ═══════════════════════════════════════

async def main():
    log.info("="*48)
    log.info("  VageGo Telegram Stream Bot v3")
    log.info("="*48)

    # Build telegram app
    tg_app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    tg_app.add_handler(CommandHandler("start", cmd_start))
    tg_app.add_handler(CommandHandler("ping",  cmd_ping))
    tg_app.add_handler(CommandHandler("myid",  cmd_myid))
    tg_app.add_handler(CommandHandler("list",  cmd_list))
    tg_app.add_handler(MessageHandler(
        filters.VIDEO | filters.Document.ALL | filters.AUDIO | filters.ANIMATION,
        on_media
    ))

    # Web server
    web_app = web.Application()
    web_app["bot"] = tg_app.bot
    web_app.router.add_get    ("/",                    handle_index)
    web_app.router.add_get    ("/health",              handle_health)
    web_app.router.add_get    ("/stream/{message_id}", handle_stream)
    web_app.router.add_options("/stream/{message_id}", handle_options)

    runner = web.AppRunner(web_app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    log.info(f"✅ Web server ready on port {PORT}")

    # Start bot polling
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling(drop_pending_updates=True)

    me = await tg_app.bot.get_me()
    log.info(f"✅ Bot: @{me.username} (ID: {me.id})")
    log.info(f"👤 Owner: {OWNER_ID}")
    log.info("🚀 LIVE! Send /start to your bot.")
    log.info("="*48)

    # Keep running
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await tg_app.updater.stop()
        await tg_app.stop()
        await tg_app.shutdown()
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
