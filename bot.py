import os
import aiohttp
import asyncio
from datetime import datetime, date
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
API_BASE = "https://v3.football.api-sports.io"

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

# League IDs
LEAGUES = {
    "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": 39,
    "🇪🇸 La Liga": 140,
    "🇩🇪 Bundesliga": 78,
    "🇮🇹 Serie A": 135,
    "🇫🇷 Ligue 1": 61,
    "🇳🇱 Eredivisie": 88,
    "🇵🇹 Liga Portugal": 94,
    "🏆 Champions League": 2,
}

LEAGUE_IDS = {v: k for k, v in LEAGUES.items()}
CURRENT_SEASON = 2024

async def api_request(endpoint: str, params: dict = {}):
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_BASE}/{endpoint}", headers=headers, params=params) as resp:
            return await resp.json()

# ===== KEYBOARDS =====

def main_menu_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🏆 Standings", callback_data="menu_standings"),
        InlineKeyboardButton("⚽ Today's Matches", callback_data="menu_today"),
        InlineKeyboardButton("📊 Results", callback_data="menu_results"),
        InlineKeyboardButton("👑 Top Scorers", callback_data="menu_scorers"),
    )
    return kb

def leagues_kb(action: str):
    kb = InlineKeyboardMarkup(row_width=2)
    for name, lid in LEAGUES.items():
        kb.add(InlineKeyboardButton(name, callback_data=f"{action}:{lid}"))
    kb.add(InlineKeyboardButton("◀️ Back", callback_data="main_menu"))
    return kb

def back_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("◀️ Back to Menu", callback_data="main_menu"))
    return kb

# ===== HANDLERS =====

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    text = (
        "⚽ <b>Football Insider</b>\n\n"
        "Your go-to source for football statistics!\n\n"
        "• 🏆 League standings in real-time\n"
        "• ⚽ Today's matches & schedule\n"
        "• 📊 Latest results\n"
        "• 👑 Top scorers\n\n"
        "Select an option below:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb())

@dp.callback_query_handler(lambda c: c.data == "main_menu")
async def cb_main_menu(callback: types.CallbackQuery):
    text = (
        "⚽ <b>Football Insider</b>\n\n"
        "Select an option:"
    )
    await callback.message.answer(text, parse_mode="HTML", reply_markup=main_menu_kb())
    await callback.answer()

# --- STANDINGS ---
@dp.callback_query_handler(lambda c: c.data == "menu_standings")
async def cb_menu_standings(callback: types.CallbackQuery):
    await callback.message.answer("🏆 <b>Standings</b>\n\nSelect a league:", parse_mode="HTML", reply_markup=leagues_kb("standings"))
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("standings:"))
async def cb_standings(callback: types.CallbackQuery):
    league_id = int(callback.data.split(":")[1])
    league_name = LEAGUE_IDS.get(league_id, "League")
    await callback.message.answer(f"⏳ Loading standings for {league_name}...", reply_markup=back_kb())
    await callback.answer()
    
    data = await api_request("standings", {"league": league_id, "season": CURRENT_SEASON})
    
    if not data.get("response"):
        await callback.message.answer("❌ No data available.", reply_markup=back_kb())
        return
    
    standings = data["response"][0]["league"]["standings"][0]
    
    text = f"🏆 <b>{league_name} — Standings</b>\n\n"
    text += f"<code>{'Pos':<4} {'Team':<22} {'Pts':>3} {'W':>3} {'D':>3} {'L':>3}</code>\n"
    text += "<code>" + "─" * 38 + "</code>\n"
    
    for team in standings[:15]:
        pos = team["rank"]
        name = team["team"]["name"][:20]
        pts = team["points"]
        w = team["all"]["win"]
        d = team["all"]["draw"]
        l = team["all"]["lose"]
        text += f"<code>{pos:<4} {name:<22} {pts:>3} {w:>3} {d:>3} {l:>3}</code>\n"
    
    await callback.message.answer(text, parse_mode="HTML", reply_markup=back_kb())

# --- TODAY'S MATCHES ---
@dp.callback_query_handler(lambda c: c.data == "menu_today")
async def cb_menu_today(callback: types.CallbackQuery):
    await callback.message.answer("⚽ <b>Today's Matches</b>\n\nSelect a league:", parse_mode="HTML", reply_markup=leagues_kb("today"))
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("today:"))
async def cb_today(callback: types.CallbackQuery):
    league_id = int(callback.data.split(":")[1])
    league_name = LEAGUE_IDS.get(league_id, "League")
    today = date.today().strftime("%Y-%m-%d")
    
    await callback.message.answer(f"⏳ Loading today's matches...", reply_markup=back_kb())
    await callback.answer()
    
    data = await api_request("fixtures", {"league": league_id, "season": CURRENT_SEASON, "date": today})
    
    if not data.get("response"):
        await callback.message.answer(f"⚽ <b>{league_name}</b>\n\nNo matches scheduled for today.", parse_mode="HTML", reply_markup=back_kb())
        return
    
    text = f"⚽ <b>{league_name} — Today's Matches</b>\n<i>{today}</i>\n\n"
    
    for fixture in data["response"]:
        home = fixture["teams"]["home"]["name"]
        away = fixture["teams"]["away"]["name"]
        status = fixture["fixture"]["status"]["short"]
        time = fixture["fixture"]["date"][11:16]
        
        if status == "NS":
            text += f"🕐 <b>{time}</b>  {home} vs {away}\n"
        elif status == "FT":
            gh = fixture["goals"]["home"]
            ga = fixture["goals"]["away"]
            text += f"✅ {home} <b>{gh}-{ga}</b> {away}\n"
        elif status in ["1H", "2H", "HT"]:
            gh = fixture["goals"]["home"]
            ga = fixture["goals"]["away"]
            text += f"🔴 LIVE  {home} <b>{gh}-{ga}</b> {away}\n"
        else:
            text += f"📅 {home} vs {away}\n"
    
    await callback.message.answer(text, parse_mode="HTML", reply_markup=back_kb())

# --- RESULTS ---
@dp.callback_query_handler(lambda c: c.data == "menu_results")
async def cb_menu_results(callback: types.CallbackQuery):
    await callback.message.answer("📊 <b>Recent Results</b>\n\nSelect a league:", parse_mode="HTML", reply_markup=leagues_kb("results"))
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("results:"))
async def cb_results(callback: types.CallbackQuery):
    league_id = int(callback.data.split(":")[1])
    league_name = LEAGUE_IDS.get(league_id, "League")
    
    await callback.message.answer(f"⏳ Loading recent results...", reply_markup=back_kb())
    await callback.answer()
    
    data = await api_request("fixtures", {
        "league": league_id,
        "season": CURRENT_SEASON,
        "status": "FT",
        "last": 10
    })
    
    if not data.get("response"):
        await callback.message.answer("❌ No results available.", reply_markup=back_kb())
        return
    
    text = f"📊 <b>{league_name} — Recent Results</b>\n\n"
    
    for fixture in data["response"]:
        home = fixture["teams"]["home"]["name"]
        away = fixture["teams"]["away"]["name"]
        gh = fixture["goals"]["home"]
        ga = fixture["goals"]["away"]
        match_date = fixture["fixture"]["date"][:10]
        text += f"📅 <i>{match_date}</i>\n{home} <b>{gh}-{ga}</b> {away}\n\n"
    
    await callback.message.answer(text, parse_mode="HTML", reply_markup=back_kb())

# --- TOP SCORERS ---
@dp.callback_query_handler(lambda c: c.data == "menu_scorers")
async def cb_menu_scorers(callback: types.CallbackQuery):
    await callback.message.answer("👑 <b>Top Scorers</b>\n\nSelect a league:", parse_mode="HTML", reply_markup=leagues_kb("scorers"))
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("scorers:"))
async def cb_scorers(callback: types.CallbackQuery):
    league_id = int(callback.data.split(":")[1])
    league_name = LEAGUE_IDS.get(league_id, "League")
    
    await callback.message.answer(f"⏳ Loading top scorers...", reply_markup=back_kb())
    await callback.answer()
    
    data = await api_request("players/topscorers", {"league": league_id, "season": CURRENT_SEASON})
    
    if not data.get("response"):
        await callback.message.answer("❌ No data available.", reply_markup=back_kb())
        return
    
    text = f"👑 <b>{league_name} — Top Scorers</b>\n\n"
    
    for i, item in enumerate(data["response"][:10], 1):
        player = item["player"]["name"]
        team = item["statistics"][0]["team"]["name"]
        goals = item["statistics"][0]["goals"]["total"]
        assists = item["statistics"][0]["goals"]["assists"] or 0
        text += f"{i}. <b>{player}</b> ({team})\n   ⚽ {goals} goals  🎯 {assists} assists\n\n"
    
    await callback.message.answer(text, parse_mode="HTML", reply_markup=back_kb())

@dp.message_handler()
async def handle_message(message: types.Message):
    await message.answer("Use the menu to navigate 👇", reply_markup=main_menu_kb())

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
