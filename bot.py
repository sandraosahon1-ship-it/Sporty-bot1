import os
import logging
import asyncio
import random
from datetime import datetime, time
import httpx
from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, JobQueue
)

BOT_TOKEN = "8584463479:AAFur-O99NibvM6qvn7P6dITV5XGt_rgVVs"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

subscribers: set = set()

SAMPLE_FIXTURES = [
    {"home": "Bayern Munich", "away": "Eintracht Frankfurt", "league": "Bundesliga", "date": "Today"},
    {"home": "Barcelona", "away": "Levante", "league": "La Liga", "date": "Today"},
    {"home": "Chelsea", "away": "Burnley", "league": "EPL", "date": "Today"},
    {"home": "PSG", "away": "Metz", "league": "Ligue 1", "date": "Today"},
    {"home": "Inter Milan", "away": "Lecce", "league": "Serie A", "date": "Today"},
    {"home": "Tottenham", "away": "Arsenal", "league": "EPL", "date": "Tomorrow"},
    {"home": "Real Madrid", "away": "Osasuna", "league": "La Liga", "date": "Tomorrow"},
    {"home": "AC Milan", "away": "Parma", "league": "Serie A", "date": "Tomorrow"},
    {"home": "RB Leipzig", "away": "Dortmund", "league": "Bundesliga", "date": "Tomorrow"},
    {"home": "Atletico Madrid", "away": "Club Brugge", "league": "UCL", "date": "Tomorrow"},
    {"home": "Newcastle", "away": "Qarabag", "league": "UCL", "date": "Tomorrow"},
    {"home": "Juventus", "away": "Galatasaray", "league": "UCL", "date": "This Week"},
    {"home": "Atalanta", "away": "Napoli", "league": "Serie A", "date": "This Week"},
    {"home": "LAFC", "away": "Inter Miami", "league": "MLS", "date": "This Week"},
    {"home": "Man City", "away": "Newcastle", "league": "EPL", "date": "This Week"},
]

def predict_match(home, away):
    seed = sum(ord(c) for c in home + away)
    rng = random.Random(seed)
    home_win = rng.randint(35, 75)
    draw = rng.randint(15, 30)
    away_win = 100 - home_win - draw
    if away_win < 5:
        away_win = 5
        home_win = 100 - draw - away_win
    return {
        "result": f"🏠 {home} Win" if home_win > away_win and home_win > draw else (f"✈️ {away} Win" if away_win > home_win else "🤝 Draw"),
        "confidence": "High" if max(home_win, away_win) > 60 else "Medium",
        "home_win": home_win, "draw": draw, "away_win": away_win,
        "over_15": rng.randint(72, 97),
        "over_25": rng.randint(50, 82),
        "over_35": rng.randint(28, 55),
        "btts": rng.randint(45, 78),
        "home_scores": rng.randint(55, 85),
        "away_scores": rng.randint(40, 72),
        "cs_home": rng.randint(20, 45),
        "cs_away": rng.randint(12, 35),
        "ht_over": rng.randint(38, 68),
    }

def format_prediction(home, away, league, pred):
    return f"""
⚽ *{home} vs {away}*
🏆 _{league}_
━━━━━━━━━━━━━━━━━━━━
📊 *MATCH RESULT*
🏠 {home}: {pred['home_win']}%
🤝 Draw: {pred['draw']}%
✈️ {away}: {pred['away_win']}%
🎯 Prediction: *{pred['result']}* ({pred['confidence']} confidence)
━━━━━━━━━━━━━━━━━━━━
🔢 *GOALS MARKETS*
Over 1.5 goals: *{pred['over_15']}%*
Over 2.5 goals: *{pred['over_25']}%*
Over 3.5 goals: *{pred['over_35']}%*
Half-Time O0.5: *{pred['ht_over']}%*
━━━━━━━━━━━━━━━━━━━━
⚡ *BOTH TEAMS TO SCORE*
BTTS Yes: *{pred['btts']}%*
BTTS No: *{100 - pred['btts']}%*
━━━━━━━━━━━━━━━━━━━━
🧹 *CLEAN SHEETS*
{home} CS: {pred['cs_home']}%
{away} CS: {pred['cs_away']}%
━━━━━━━━━━━━━━━━━━━━
🎯 *TEAM TO SCORE*
{home} to score: {pred['home_scores']}%
{away} to score: {pred['away_scores']}%
━━━━━━━━━━━━━━━━━━━━
⚠️ _For entertainment only. Bet responsibly._
"""

def get_top_picks(market="over_15", n=5):
    scored = sorted([(predict_match(f["home"], f["away"])[market], f, predict_match(f["home"], f["away"])) for f in SAMPLE_FIXTURES], reverse=True)
    labels = {"over_15": "⚽ Over 1.5 Goals", "over_25": "⚽ Over 2.5 Goals", "over_35": "⚽ Over 3.5 Goals", "btts": "⚡ BTTS"}
    label = labels.get(market, market)
    lines = [f"🔥 *Top {n} {label} Picks*\n━━━━━━━━━━━━━━━━━━━━"]
    for i, (pct, f, pred) in enumerate(scored[:n], 1):
        lines.append(f"{i}. *{f['home']} vs {f['away']}*\n   🏆 {f['league']} | 📅 {f['date']}\n   {label}: *{pct}%* | {pred['result']}\n")
    lines.append("⚠️ _Bet responsibly. 18+ only._")
    return "\n".join(lines)

async def ask_claude(question):
    if not ANTHROPIC_API_KEY:
        return "🤖 AI chat unavailable. Use /picks, /predict, /today or /help!"
    headers = {"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    payload = {
        "model": "claude-sonnet-4-20250514", "max_tokens": 600,
        "system": "You are Sporty Predictor, an expert soccer betting analyst bot on Telegram. Help users with match predictions, betting markets (over/under, BTTS, match result, Asian handicap, corners, cards), team form, and betting strategy. Be concise, use emojis, always remind users to bet responsibly.",
        "messages": [{"role": "user", "content": question}],
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
            return r.json()["content"][0]["text"]
    except Exception as e:
        return "⚠️ AI is taking a break. Try /picks or /predict!"

async def start(update, ctx):
    name = update.effective_user.first_name
    await update.message.reply_text(f"👋 Welcome *{name}*! I'm *Sporty Predictor Bot* ⚽\n\n📋 *Commands:*\n/today — Today's picks\n/picks — Over 1.5 picks\n/over25 — Over 2.5 picks\n/over35 — Over 3.5 picks\n/btts — BTTS picks\n/predict TeamA vs TeamB\n/leagues — Covered leagues\n/subscribe — Daily picks\n/help — All commands\n\n💬 Or just ask me anything!\n\n⚠️ _Bet responsibly. 18+ only._", parse_mode="Markdown")

async def help_cmd(update, ctx):
    await update.message.reply_text("📋 *Commands*\n\n/today — Today's picks\n/picks — Over 1.5\n/over25 — Over 2.5\n/over35 — Over 3.5\n/btts — Both Teams Score\n/predict TeamA vs TeamB\n/leagues — Supported leagues\n/subscribe — Daily 8AM picks\n/unsubscribe — Stop picks\n\n💬 Or type any question naturally!", parse_mode="Markdown")

async def today_picks(update, ctx):
    await update.message.reply_text("⏳ Analyzing fixtures...")
    today = [f for f in SAMPLE_FIXTURES if f["date"] == "Today"] or SAMPLE_FIXTURES[:4]
    msg = "📅 *TODAY'S PREDICTIONS*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for f in today:
        pred = predict_match(f["home"], f["away"])
        msg += f"⚽ *{f['home']} vs {f['away']}*\n🏆 {f['league']}\n🎯 {pred['result']}\n📈 O1.5: *{pred['over_15']}%* | O2.5: *{pred['over_25']}%*\n⚡ BTTS: *{pred['btts']}%*\n\n"
    msg += "⚠️ _Bet responsibly. 18+ only._"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def picks_over15(update, ctx):
    await update.message.reply_text("⏳ Getting picks...")
    await update.message.reply_text(ge
async def picks_over25(update, ctx):
    await update.message.reply_text("⏳ Getting picks...")
    await update.message.reply_text(get_top_picks("over_25", 6), parse_mode="Markdown")

async def picks_over35(update, ctx):
    await update.message.reply_text("⏳ Getting picks...")
    await update.message.reply_text(get_top_picks("over_35", 6), parse_mode="Markdown")

async def picks_btts(update, ctx):
    await update.message.reply_text("⏳ Getting picks...")
    await update.message.reply_text(get_top_picks("btts", 6), parse_mode="Markdown")

async def predict_cmd(update, ctx):
    text = update.message.text.replace("/predict", "").strip()
    if " vs " not in text.lower():
        await update.message.reply_text("📝 Usage: `/predict TeamA vs TeamB`\nExample: `/predict Liverpool vs Arsenal`", parse_mode="Markdown")
        return
    parts = text.lower().split(" vs ")
    home, away = parts[0].strip().title(), parts[1].strip().title()
    league = next((f["league"] for f in SAMPLE_FIXTURES if f["home"].lower() in home.lower()), "International")
    await update.message.reply_text("🔮 Generating prediction...")
    pred = predict_match(home, away)
    await update.message.reply_text(format_prediction(home, away, league, pred), parse_mode="Markdown")

async def leagues_cmd(update, ctx):
    await update.message.reply_text("🌍 *Supported Leagues*\n\n🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League\n🇪🇸 La Liga\n🇩🇪 Bundesliga\n🇮🇹 Serie A\n🇫🇷 Ligue 1\n🇵🇹 Primeira Liga\n🇳🇱 Eredivisie\n🇺🇸 MLS\n⭐ Champions League\n🏆 Europa League", parse_mode="Markdown")

async def subscribe_cmd(update, ctx):
    subscribers.add(update.effective_chat.id)
    await update.message.reply_text("✅ *Subscribed!* Daily picks at *8AM* every morning ⚽\nUse /unsubscribe to stop.", parse_mode="Markdown")

async def unsubscribe_cmd(update, ctx):
    subscribers.discard(update.effective_chat.id)
    await update.message.reply_text("❌ Unsubscribed from daily picks.")

async def handle_message(update, ctx):
    await update.message.reply_text("🤔 Analyzing...")
    response = await ask_claude(update.message.text)
    await update.message.reply_text(response, parse_mode="Markdown")

async def daily_picks_job(ctx):
    if not subscribers: return
    msg = "🌅 *GOOD MORNING! Daily Picks* ⚽\n\n" + get_top_picks("over_15", 5) + "\n\n" + get_top_picks("btts", 3)
    for uid in list(subscribers):
        try: await ctx.bot.send_message(chat_id=uid, text=msg, parse_mode="Markdown")
        except: subscribers.discard(uid)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("today", today_picks))
    app.add_handler(CommandHandler("picks", picks_over15))
    app.add_handler(CommandHandler("over25", picks_over25))
    app.add_handler(CommandHandler("over35", picks_over35))
    app.add_handler(CommandHandler("btts", picks_btts))
    app.add_handler(CommandHandler("predict", predict_cmd))
    app.add_handler(CommandHandler("leagues", leagues_cmd))
    app.add_handler(CommandHandler("subscribe", subscribe_cmd))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.job_queue.run_daily(daily_picks_job, time=time(hour=8, minute=0))
    print("🤖 Sporty Predictor Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
