import os, asyncio, logging, sys, time, json
from pathlib import Path
from aiohttp import web
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

logging.basicConfig(level=logging.INFO, stream=sys.stdout,
    format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("VageGo")

API_ID       = os.environ.get("API_ID", "")
API_HASH     = os.environ.get("API_HASH", "")
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
OWNER_ID     = int(os.environ.get("OWNER_ID", "0"))
BASE_URL     = os.environ.get("BASE_URL", "").rstrip("/")
PORT         = int(os.environ.get("PORT", "8080"))

missing = [k for k,v in {"API_ID":API_ID,"API_HASH":API_HASH,"BOT_TOKEN":BOT_TOKEN}.items() if not v]
if missing:
    log.error(f"MISSING ENV VARS: {', '.join(missing)}")
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

# ── KEY FIX: workdir session instead of in_memory ──
bot = Client(
    name="vagego_bot",
    api_id=int(API_ID),
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir="/tmp",          # session file /tmp/vagego_bot.session
)

def fmt_size(n):
    for u in ["B","KB","MB","GB"]:
        if n < 1024: return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"

def make_url(key):
    return f"{BASE_URL or f'http://localhost:{PORT}'}/stream/{key}"

def is_owner(msg):
    if not OWNER_ID: return True
    return msg.from_user and msg.from_user.id == OWNER_ID

# ══ COMMANDS ══════════════════════════════════════

@bot.on_message(filters.command("start") & filters.private)
async def cmd_start(_, msg: Message):
    name = msg.from_user.first_name if msg.from_user else "User"
    await msg.reply_text(
        f"👋 **Hello {name}!**\n\n"
        "🎬 **VageGo Stream Bot**\n\n"
        "✅ যেকোনো **video forward** করুন\n"
        "🔗 সাথে সাথে **Stream Link** পাবেন!\n\n"
        f"📁 Cached: `{len(FILE_STORE)}` files",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🎬 VageGo App", url="https://vagego.netlify.app")
        ]])
    )

@bot.on_message(filters.command("ping") & filters.private)
async def cmd_ping(_, msg: Message):
    t = time.monotonic()
    m = await msg.reply_text("🏓 Pinging...")
    ms = round((time.monotonic() - t) * 1000)
    await m.edit_text(f"🏓 **Pong!** `{ms}ms`\n✅ Bot Online\n📁 Cached: `{len(FILE_STORE)}`")

@bot.on_message(filters.command("myid") & filters.private)
async def cmd_myid(_, msg: Message):
    await msg.reply_text(f"🆔 Your ID: `{msg.from_user.id}`")

@bot.on_message(filters.command("list") & filters.private)
async def cmd_list(_, msg: Message):
    if not is_owner(msg): return
    if not FILE_STORE:
        await msg.reply_text("📭 কোনো cached file নেই।")
        return
    lines = [f"📁 **Cached ({len(FILE_STORE)}):**\n"]
    for i, (k, v) in enumerate(list(FILE_STORE.items())[-10:], 1):
        lines.append(f"{i}. `{v['file_name']}`\n`{make_url(k)}`")
    await msg.reply_text("\n".join(lines))

# ══ MAIN FEATURE ══════════════════════════════════

@bot.on_message(
    filters.private &
    (filters.video | filters.document | filters.audio | filters.animation)
)
async def on_media(_, msg: Message):
    if not is_owner(msg):
        await msg.reply_text(f"🔒 শুধু owner ব্যবহার করতে পারবে।\nআপনার ID: `{msg.from_user.id}`")
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
            "file_id": file_id, "file_name": file_name,
            "mime_type": mime_type, "file_size": file_size,
        }
        save_store(FILE_STORE)

        url = make_url(key)

        await proc.edit_text(
            f"✅ **Stream Link Ready!**\n\n"
            f"📁 **File:** `{file_name}`\n"
            f"📦 **Size:** {fmt_size(file_size)}\n\n"
            f"🔗 **Stream URL:**\n`{url}`\n\n"
            f"➡️ এই URL VageGo Admin Panel এ paste করুন",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("▶ Test করুন", url=url)
            ]])
        )
        log.info(f"Link ready: {url} | {file_name}")

    except FloodWait as e:
        await asyncio.sleep(e.value)
        await proc.edit_text(f"⚠️ Rate limit। {e.value}s পর চেষ্টা করুন।")
    except Exception as e:
        log.error(f"on_media error: {e}", exc_info=True)
        await proc.edit_text(f"❌ Error: `{str(e)[:300]}`")

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
        return web.Response(text=f"File '{key}' not found. Video আবার পাঠান।", status=404)

    info = FILE_STORE[key]
    file_id, file_name = info["file_id"], info["file_name"]
    mime_type, file_size = info["mime_type"], info["file_size"]

    rh = req.headers.get("Range","")
    start, end = 0, max(file_size-1, 0)
    if rh and "=" in rh:
        try:
            p = rh.split("=",1)[1].split("-",1)
            start = int(p[0].strip()) if p[0].strip() else 0
            end   = int(p[1].strip()) if len(p)>1 and p[1].strip() else max(file_size-1,0)
        except: pass

    cl = max(end - start + 1, 0)
    headers = {
        "Content-Type": mime_type,
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{file_name}"',
        "Access-Control-Allow-Origin": "*",
    }
    if file_size > 0:
        headers["Content-Range"]  = f"bytes {start}-{end}/{file_size}"
        headers["Content-Length"] = str(cl)

    resp = web.StreamResponse(status=206 if rh else 200, headers=headers)
    try:
        await resp.prepare(req)
    except: return resp

    try:
        sent = 0
        async for chunk in bot.stream_media(file_id, offset=start, limit=cl if cl>0 else None):
            if not chunk: continue
            try: await resp.write(chunk)
            except: break
            sent += len(chunk)
            if cl and sent >= cl: break
    except Exception as e:
        log.error(f"Stream error: {e}")

    try: await resp.write_eof()
    except: pass
    return resp

async def handle_options(req):
    return web.Response(status=200, headers={
        "Access-Control-Allow-Origin":"*",
        "Access-Control-Allow-Methods":"GET, HEAD, OPTIONS",
        "Access-Control-Allow-Headers":"Range, Content-Type",
    })

# ══ STARTUP ═══════════════════════════════════════

async def main():
    log.info("="*48)
    log.info("  VageGo Telegram Stream Bot")
    log.info("="*48)

    app = web.Application()
    app.router.add_get    ("/",                    handle_index)
    app.router.add_get    ("/health",              handle_health)
    app.router.add_get    ("/stream/{message_id}", handle_stream)
    app.router.add_options("/stream/{message_id}", handle_options)

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    log.info(f"✅ Web server ready on port {PORT}")

    try:
        await bot.start()
        me = await bot.get_me()
        log.info(f"✅ Bot: @{me.username} (ID: {me.id})")
        log.info(f"👤 Owner: {OWNER_ID}")
        log.info("🚀 LIVE! Send /start to your bot.")
        log.info("="*48)
    except Exception as e:
        log.error(f"❌ Bot start failed: {e}")
        await asyncio.Event().wait()
        return

    # ── KEY FIX: manual wait instead of idle() ──
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await bot.stop()
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
    
