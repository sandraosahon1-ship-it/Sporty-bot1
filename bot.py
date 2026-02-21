import os
import logging
import random
from datetime import time
import httpx
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = "8584463479:AAFur-O99NibvM6qvn7P6dITV5XGt_rgVVs"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

subscribers = set()

FIXTURES = [
    {"home": "Bayern Munich", "away": "Eintracht Frankfurt", "league": "Bundesliga"},
    {"home": "Barcelona", "away": "Levante", "league": "La Liga"},
    {"home": "Chelsea", "away": "Burnley", "league": "EPL"},
    {"home": "PSG", "away": "Metz", "league": "Ligue 1"},
    {"home": "Inter Milan", "away": "Lecce", "league": "Serie A"},
    {"home": "Tottenham", "away": "Arsenal", "league": "EPL"},
    {"home": "Real Madrid", "away": "Osasuna", "league": "La Liga"},
    {"home": "AC Milan", "away": "Parma", "league": "Serie A"},
    {"home": "RB Leipzig", "away": "Dortmund", "league": "Bundesliga"},
    {"home": "Atletico Madrid", "away": "Club Brugge", "league": "UCL"},
]

def predict(home, away):
    seed = sum(ord(c) for c in home + away)
    rng = random.Random(seed)
    hw = rng.randint(35, 75)
    dr = rng.randint(15, 25)
    aw = 100 - hw - dr
    if aw < 5:
        aw = 5
        hw = 100 - dr - aw
    if hw > aw and hw > dr:
        result = f"🏠 {home} Win"
    elif aw > hw and aw > dr:
        result = f"✈️ {away} Win"
    else:
        result = "🤝 Draw"
    return {
        "result": result,
        "hw": hw, "dr": dr, "aw": aw,
        "o15": rng.randint(72, 97),
        "o25": rng.randint(50, 82),
        "o35": rng.randint(28, 55),
        "btts": rng.randint(45, 78),
        "cs_h": rng.randint(20, 45),
        "cs_a": rng.randint(12, 35),
        "h_score": rng.randint(55, 85),
        "a_score": rng.randint(40, 72),
    }

def picks_msg(market, label, n=5):
    data = []
    for f in FIXTURES:
        p = predict(f["home"], f["away"])
        data.append((p[market], f, p))
    data.sort(reverse=True)
    msg = f"🔥 *Top {label} Picks*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for i, (pct, f, p) in enumerate(data[:n], 1):
        msg += f"{i}. *{f['home']} vs {f['away']}*\n"
        msg += f"   🏆 {f['league']} | {label}: *{pct}%*\n"
        msg += f"   🎯 {p['result']}\n\n"
    msg += "⚠️ _Bet responsibly. 18+ only._"
    return msg

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"👋 Welcome *{name}*! I'm *Sporty Predictor Bot* ⚽\n\n"
        "📋 *Commands:*\n"
        "/today — Today's picks\n"
        "/picks — Over 1.5 picks\n"
        "/over25 — Over 2.5 picks\n"
        "/over35 — Over 3.5 picks\n"
        "/btts — BTTS picks\n"
        "/predict TeamA vs TeamB\n"
        "/subscribe — Daily picks\n"
        "/help — All commands\n\n"
        "⚠️ _Bet responsibly. 18+ only._",
        parse_mode="Markdown"
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *All Commands*\n\n"
        "/today /picks /over25 /over35 /btts\n"
        "/predict TeamA vs TeamB\n"
        "/subscribe /unsubscribe\n\n"
        "💬 Or type any question!",
        parse_mode="Markdown"
    )

async def today_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = "📅 *TODAY'S PICKS*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for f in FIXTURES[:5]:
        p = predict(f["home"], f["away"])
        msg += f"⚽ *{f['home']} vs {f['away']}*\n"
        msg += f"🏆 {f['league']}\n"
        msg += f"🎯 {p['result']}\n"
        msg += f"Over 1.5: *{p['o15']}%* | BTTS: *{p['btts']}%*\n\n"
    msg += "⚠️ _Bet responsibly. 18+ only._"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def picks_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(picks_msg("o15", "Over 1.5 Goals"), parse_mode="Markdown")

async def over25_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(picks_msg("o25", "Over 2.5 Goals"), parse_mode="Markdown")

async def over35_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(picks_msg("o35", "Over 3.5 Goals"), parse_mode="Markdown")

async def btts_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(picks_msg("btts", "BTTS"), parse_mode="Markdown")

async def predict_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace("/predict", "").strip()
    if " vs " not in text.lower():
        await update.message.reply_text("📝 Usage: `/predict TeamA vs TeamB`", parse_mode="Markdown")
        return
    parts = text.split(" vs ")
    home = parts[0].strip().title()
    away = parts[1].strip().title()
    league = next((f["league"] for f in FIXTURES if f["home"].lower() in home.lower()), "International")
    p = predict(home, away)
    msg = (
        f"⚽ *{home} vs {away}*\n"
        f"🏆 _{league}_\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *MATCH RESULT*\n"
        f"🏠 {home}: {p['hw']}%\n"
        f"🤝 Draw: {p['dr']}%\n"
        f"✈️ {away}: {p['aw']}%\n"
        f"🎯 Prediction: *{p['result']}*\n\n"
        f"🔢 *GOALS*\n"
        f"Over 1.5: *{p['o15']}%*\n"
        f"Over 2.5: *{p['o25']}%*\n"
        f"Over 3.5: *{p['o35']}%*\n\n"
        f"⚡ *BTTS*\n"
        f"Yes: *{p['btts']}%* | No: *{100-p['btts']}%*\n\n"
        f"🧹 *CLEAN SHEETS*\n"
        f"{home}: {p['cs_h']}% | {away}: {p['cs_a']}%\n\n"
        f"⚠️ _Bet responsibly. 18+ only._"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def subscribe_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    subscribers.add(update.effective_chat.id)
    await update.message.reply_text("✅ Subscribed! Daily picks at 8AM ⚽")

async def unsubscribe_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    subscribers.discard(update.effective_chat.id)
    await update.message.reply_text("❌ Unsubscribed from daily picks.")

async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if " vs " in text:
        home, away = text.split(" vs ", 1)
        home = home.strip().title()
        away = away.strip().title()
        league = next((f["league"] for f in FIXTURES if f["home"].lower() in home.lower()), "International")
        p = predict(home, away)
        await update.message.reply_text(
            f"⚽ *{home} vs {away}* | 🏆 {league}\n"
            f"🎯 {p['result']}\n"
            f"Over 1.5: *{p['o15']}%* | Over 2.5: *{p['o25']}%*\n"
            f"BTTS: *{p['btts']}%*\n\n"
            f"⚠️ _Bet responsibly._",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "I can predict any match! Try:\n"
            "• `/predict Liverpool vs Arsenal`\n"
            "• Or type: `Liverpool vs Arsenal`\n"
            "• `/picks` for today's best bets",
            parse_mode="Markdown"
        )

async def daily_job(ctx: ContextTypes.DEFAULT_TYPE):
    if not subscribers:
        return
    msg = "🌅 *Good Morning! Daily Picks* ⚽\n\n" + picks_msg("o15", "Over 1.5 Goals", 5)
    for uid in list(subscribers):
        try:
            await ctx.bot.send_message(chat_id=uid, text=msg, parse_mode="Markdown")
        except:
            subscribers.discard(uid)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("today", today_cmd))
    app.add_handler(CommandHandler("picks", picks_cmd))
    app.add_handler(CommandHandler("over25", over25_cmd))
    app.add_handler(CommandHandler("over35", over35_cmd))
    app.add_handler(CommandHandler("btts", btts_cmd))
    app.add_handler(CommandHandler("predict", predict_cmd))
    app.add_handler(CommandHandler("subscribe", subscribe_cmd))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.job_queue.run_daily(daily_job, time=time(hour=8, minute=0))
    print("🤖 Sporty Predictor Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
