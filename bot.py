import requests
import sqlite3
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = "8533083915:AAHsWFxyQ56uyL8M50ygxyOMibAQrO5xI38"
ADMIN_ID = 7380035019
GPLINKS_API = "9b10204081fca3629abc3e6f133a21bcde4f89f4"
EMAIL_VALIDITY = 600  # 10 minutes

# DB setup
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    email TEXT,
    created_at INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link TEXT,
    username TEXT
)
""")
conn.commit()


# 🔹 Check Force Join
async def is_joined(user_id, context):
    cursor.execute("SELECT username FROM channels")
    channels = cursor.fetchall()

    for ch in channels:
        try:
            member = await context.bot.get_chat_member(chat_id=ch[0], user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except:
            return False
    return True


# 🚀 START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if context.args and context.args[0] == "email_ready":
        await generate_email(update, context)
        return

    if not await is_joined(user_id, context):
        keyboard = []
        cursor.execute("SELECT link FROM channels")
        for ch in cursor.fetchall():
            keyboard.append([InlineKeyboardButton("Join Channel", url=ch[0])])

        keyboard.append([InlineKeyboardButton("Verify", callback_data="verify")])

        await update.message.reply_text(
            "Join all channels first",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    await menu(update)


# ✅ VERIFY
async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    if await is_joined(user_id, context):
        await query.message.reply_text("Verified ✅")
        await menu(query)
    else:
        await query.answer("Join all channels!", show_alert=True)


# 📋 MENU
async def menu(update):
    keyboard = [
        [InlineKeyboardButton("Generate Email", callback_data="gen")],
        [InlineKeyboardButton("Inbox", callback_data="inbox")]
    ]

    if hasattr(update, "message"):
        await update.message.reply_text("Menu", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("Menu", reply_markup=InlineKeyboardMarkup(keyboard))


# 💰 GPLinks
async def gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    link = f"https://t.me/{context.bot.username}?start=email_ready"
    url = f"https://gplinks.in/api?api={GPLINKS_API}&url={link}"

    try:
        res = requests.get(url).json()
        short = res.get("shortenedUrl")

        await query.message.reply_text(f"Complete this:\n{short}")
    except:
        await query.message.reply_text("Error generating link")


# 📧 GENERATE EMAIL
async def generate_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    res = requests.get("https://www.1secmail.com/api/v1/?action=genRandomMailbox&count=1").json()
    email = res[0]

    cursor.execute("REPLACE INTO users VALUES (?, ?, ?)",
                   (user_id, email, int(time.time())))
    conn.commit()

    keyboard = [
        [InlineKeyboardButton("Copy Email", callback_data="copy")],
        [InlineKeyboardButton("Inbox", callback_data="inbox")]
    ]

    await update.message.reply_text(
        f"Email:\n{email}\nValid 10 min",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# 📥 INBOX
async def inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    cursor.execute("SELECT email, created_at FROM users WHERE user_id=?", (user_id,))
    data = cursor.fetchone()

    if not data:
        await query.message.reply_text("Generate email first")
        return

    email, created = data

    if time.time() - created > EMAIL_VALIDITY:
        await query.message.reply_text("Email expired")
        return

    login, domain = email.split("@")
    url = f"https://www.1secmail.com/api/v1/?action=getMessages&login={login}&domain={domain}"

    msgs = requests.get(url).json()

    if not msgs:
        await query.message.reply_text("Inbox empty")
        return

    text = ""
    for m in msgs:
        text += f"From: {m['from']}\nSubject: {m['subject']}\n\n"

    await query.message.reply_text(text)


# 📋 COPY
async def copy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id

    cursor.execute("SELECT email FROM users WHERE user_id=?", (user_id,))
    data = cursor.fetchone()

    if data:
        await query.answer(data[0], show_alert=True)


# ⚙️ ADMIN
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    keyboard = [
        [InlineKeyboardButton("Add Channel", callback_data="add")],
        [InlineKeyboardButton("View Channels", callback_data="view")]
    ]

    await update.message.reply_text("Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))


# ➕ ADD CHANNEL
async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    msg = update.message.text.split(" ")

    if len(msg) < 3:
        await update.message.reply_text("Use:\n/addchannel link username")
        return

    cursor.execute("INSERT INTO channels (link, username) VALUES (?, ?)",
                   (msg[1], msg[2]))
    conn.commit()

    await update.message.reply_text("Added ✅")


# 📋 VIEW CHANNELS
async def view_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("SELECT link FROM channels")
    data = cursor.fetchall()

    text = "\n".join([d[0] for d in data]) if data else "No channels"
    await update.callback_query.message.reply_text(text)


# 🔁 BUTTON HANDLER
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data

    if data == "verify":
        await verify(update, context)
    elif data == "gen":
        await gen(update, context)
    elif data == "inbox":
        await inbox(update, context)
    elif data == "copy":
        await copy(update, context)
    elif data == "view":
        await view_channels(update, context)


# 🚀 MAIN
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("admin", admin))
app.add_handler(CommandHandler("addchannel", add_channel))
app.add_handler(CallbackQueryHandler(buttons))

print("Bot Running...")
app.run_polling()