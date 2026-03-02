import asyncio, os, logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

from database import *
from music_api import *
from audio_processor import *

load_dotenv()
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

USER_SEARCHES = {}

class AdminState(StatesGroup):
    waiting_for_broadcast = State()

LANGS = {
    'uz': {'welcome': "👋 Salom! Musiqa nomini yozing yoki ovoz yuboring.", 'search': "🔍 Qidirilmoqda...", 'not_found': "❌ Afsuski, topilmadi."},
    'kr': {'welcome': "👋 Салом! Мусиқа номини ёзинг ёки овоз юборинг.", 'search': "🔍 Қидирилмоқда...", 'not_found': "❌ Афсуски, топилмади."},
    'ru': {'welcome': "👋 Привет! Напишите название музыки или отправьте голосовое сообщение.", 'search': "🔍 Поиск...", 'not_found': "❌ Не найдено."},
    'en': {'welcome': "👋 Hello! Send a song name or voice message.", 'search': "🔍 Searching...", 'not_found': "❌ Not found."}
}

def lang_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇿 O'zbekcha", callback_data="lang_uz")
    builder.button(text="🇺🇿 Ўзбекча", callback_data="lang_kr")
    builder.button(text="🇷🇺 Русский", callback_data="lang_ru")
    builder.button(text="🇬🇧 English", callback_data="lang_en")
    builder.adjust(2)
    return builder.as_markup()

def get_search_keyboard(user_id, page=0):
    results = USER_SEARCHES.get(user_id, {}).get('results', [])
    total_pages = (len(results) + 5) // 6
    builder = InlineKeyboardBuilder()
    
    start, end = page * 6, (page + 1) * 6
    current_results = results[start:end]
    
    for i, _ in enumerate(current_results):
        builder.button(text=str(i+1), callback_data=f"dl_{start+i}")
    
    builder.adjust(5, 1) 
    builder.row(
        types.InlineKeyboardButton(text="⬅️", callback_data=f"p_{page-1}" if page > 0 else "noop"),
        types.InlineKeyboardButton(text="❌", callback_data="del"),
        types.InlineKeyboardButton(text="➡️", callback_data=f"p_{page+1}" if page < total_pages - 1 else "noop")
    )
    return builder.as_markup()

def get_actions_kb(q_key, user_id, bot_name):
    favs = get_favorites(user_id)
    builder = InlineKeyboardBuilder()
    builder.button(text="🎧 8D", callback_data=f"8d_{q_key}")
    builder.button(text="🏟 Concert Hall", callback_data=f"ch_{q_key}")
    builder.button(text="🐢 Slowed", callback_data=f"sl_{q_key}")
    builder.button(text="📝 Tekst", callback_data=f"ly_{q_key}")
    builder.button(text="💔 Olib tashlash" if q_key in favs else "❤️ Saqlash", callback_data=f"fv_{q_key}")
    builder.button(text="➕ Guruhga qo'shish", url=f"https://t.me/{bot_name}?startgroup=true")
    builder.adjust(2, 1, 2, 1) 
    return builder.as_markup()

@dp.message(Command("start"))
async def start(m: types.Message):
    is_new = add_user(m.from_user.id)
    if is_new and ADMIN_ID != 0:
        try: await bot.send_message(chat_id=ADMIN_ID, text="🎉 Yangi obunachi qo'shildi!")
        except: pass

    lang = get_lang(m.from_user.id)
    if not lang:
        await m.answer("🇺🇿 Tilni tanlang\n🇷🇺 Выберите язык\n🇬🇧 Choose language:", reply_markup=lang_keyboard())
    else:
        await m.answer(LANGS[lang]['welcome'])

@dp.callback_query(F.data.startswith("lang_"))
async def set_user_lang(c: CallbackQuery):
    lang = c.data.split("_")[1]
    set_lang(c.from_user.id, lang)
    await c.message.edit_text(LANGS[lang]['welcome'])

# --- ADMIN PANEL YANGILANDI ---
@dp.message(Command("admin"))
async def admin(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    u, c = get_stats()
    today_dl = get_daily_downloads() # Bugungi yuklanishlarni olamiz
    kb = InlineKeyboardBuilder().button(text="📢 Xabar yuborish", callback_data="bc").as_markup()
    
    text = (f"👮‍♂️ **Admin Panel**\n\n"
            f"👥 Jami a'zolar: {u}\n"
            f"🎵 Bazadagi musiqalar: {c}\n"
            f"📈 **Bugun yuklandi:** {today_dl} ta musiqa")
            
    await m.answer(text, reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "bc")
async def bc(c: CallbackQuery, s: FSMContext):
    await c.message.answer("Tarqatmoqchi bo'lgan xabaringizni yuboring:"); await s.set_state(AdminState.waiting_for_broadcast)

@dp.message(AdminState.waiting_for_broadcast)
async def bc_p(m: types.Message, s: FSMContext):
    for u in get_all_users():
        try: await m.copy_to(u); await asyncio.sleep(0.05)
        except: pass
    await m.answer("✅ Xabar barchaga yuborildi!"); await s.clear()

@dp.message(Command("top"))
async def show_top(m: types.Message):
    tops = get_top_songs(10)
    if not tops: return await m.answer("Hozircha top musiqalar yo'q.")
    text = "🔥 **Eng ommabop musiqalar:**\n\n"
    kb = InlineKeyboardBuilder()
    for i, (title, q_key) in enumerate(tops):
        text += f"**{i+1}.** {title}\n"
        kb.button(text=str(i+1), callback_data=f"sendc_{q_key}")
    kb.adjust(5)
    await m.answer(text, reply_markup=kb.as_markup(), parse_mode="Markdown")

@dp.message(Command("fav"))
async def show_favs(m: types.Message):
    favs = get_favorites(m.from_user.id)
    if not favs: return await m.answer("❤️ Sevimli musiqalaringiz yo'q.")
    text = "❤️ **Sizning musiqalaringiz:**\n\n"
    kb = InlineKeyboardBuilder()
    for i, q_key in enumerate(favs[:20]):
        text += f"**{i+1}.** {q_key.capitalize()}\n"
        kb.button(text=str(i+1), callback_data=f"sendc_{q_key}")
    kb.adjust(5)
    await m.answer(text, reply_markup=kb.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("sendc_"))
async def send_cached_audio(c: CallbackQuery):
    q_key = c.data.replace("sendc_", "")
    f_id = get_cache(q_key)
    if f_id:
        b = await bot.get_me()
        await bot.send_audio(c.from_user.id, f_id, caption=f"🎧 Musiqa\n🤖 @{b.username}", reply_markup=get_actions_kb(q_key, c.from_user.id, b.username))
        increment_daily_download() # Statistika +1
    await c.answer()

@dp.message(F.text | F.voice | F.audio)
async def search(m: types.Message, state: FSMContext):
    if await state.get_state() == AdminState.waiting_for_broadcast.state: return
    if m.text and m.text.startswith("/"): return
    
    lang = get_lang(m.from_user.id) or 'uz'
    msg = await m.answer(LANGS[lang]['search'])
    
    if m.voice or m.audio:
        file_id = m.voice.file_id if m.voice else m.audio.file_id
        file = await bot.get_file(file_id)
        temp_path = f"downloads/{file_id}.ogg"
        await bot.download_file(file.file_path, destination=temp_path)
        
        query = await recognize_song(temp_path)
        os.remove(temp_path)
        if not query: return await msg.edit_text(LANGS[lang]['not_found'])
    else:
        query = m.text
        
    res = search_combined(query) 
    if not res: return await msg.edit_text(LANGS[lang]['not_found'])
    
    USER_SEARCHES[m.from_user.id] = {'results': res, 'query': query, 'page': 0}
    await send_p(m.from_user.id, 0, msg)

async def send_p(uid, p, msg):
    d = USER_SEARCHES[uid]; r = d['results'][p*6:(p+1)*6]
    t = f"🔍 **{d['query']}** natijalari:\n\n"
    for i, x in enumerate(r): t += f"**{i+1}.** {x['title']}\n"
    await msg.edit_text(t + "\nIltimos, o'zingizga kerakli variantni tanlang 👇", reply_markup=get_search_keyboard(uid, p), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("p_"))
async def p_nav(c: CallbackQuery):
    p = int(c.data.split("_")[1]); await send_p(c.from_user.id, p, c.message)

@dp.callback_query(F.data.startswith("dl_"))
async def dl(c: CallbackQuery):
    idx = int(c.data.split("_")[1]); d = USER_SEARCHES[c.from_user.id]['results'][idx]
    q_key = "".join(x for x in d['title'][:15] if x.isalnum()).lower()
    await c.message.edit_text(f"⏳ **{d['title']}** yuklanmoqda..."); b = await bot.get_me()
    
    cached = get_cache(q_key)
    cap = f"🎧 Musiqa: {d['title']}\n\n🤖 @{b.username} orqali istagan musiqangizni tez va oson toping!🚀"
    
    if cached:
        await bot.send_audio(c.from_user.id, cached, caption=cap, reply_markup=get_actions_kb(q_key, c.from_user.id, b.username))
        increment_daily_download() # Statistika +1
    else:
        f = download_music(d['url'], f"downloads/{q_key}")
        sent = await bot.send_audio(c.from_user.id, FSInputFile(f), caption=cap, reply_markup=get_actions_kb(q_key, c.from_user.id, b.username))
        add_cache(q_key, sent.audio.file_id, d['title'])
        os.remove(f)
        increment_daily_download() # Statistika +1
    await c.message.delete()

@dp.callback_query(F.data == "del")
async def d_m(c: CallbackQuery): await c.message.delete()

@dp.callback_query(F.data == "noop")
async def noop(c: CallbackQuery): await c.answer()

@dp.callback_query(F.data.startswith("fv_"))
async def fav(c: CallbackQuery):
    q_key = c.data.replace("fv_", ""); b = await bot.get_me()
    is_fav = toggle_favorite(c.from_user.id, q_key)
    if is_fav: await c.answer("❤️ Sevimlilarga qo'shildi!", show_alert=True)
    else: await c.answer("💔 Olib tashlandi!", show_alert=True)
    await c.message.edit_reply_markup(reply_markup=get_actions_kb(q_key, c.from_user.id, b.username))

@dp.callback_query(F.data.startswith(("8d_", "sl_", "ch_", "ly_")))
async def effects(c: CallbackQuery):
    act, q_key = c.data.split("_", 1); await c.answer("⏳ Jarayonda..."); b = await bot.get_me()
    
    if act == "ly": return await c.message.reply("📝 Qo'shiq matnlarini topish tizimi tez orada ishga tushadi!", parse_mode="Markdown")
    
    f_id = get_cache(f"orig_{q_key}") or get_cache(q_key)
    if not f_id: return await c.answer("❌ Keshda topilmadi.", show_alert=True)
    
    file = await bot.get_file(f_id); tmp, out = f"downloads/t_{q_key}.mp3", f"downloads/{act}_{q_key}.mp3"
    await bot.download_file(file.file_path, tmp)
    
    if act == "8d": make_8d(tmp, out)
    elif act == "sl": make_slowed(tmp, out)
    elif act == "ch": make_concert_hall(tmp, out)
    
    await bot.send_audio(c.from_user.id, FSInputFile(out), caption=f"✨ Effekt: {act.upper()}\n🤖 @{b.username}")
    os.remove(tmp); os.remove(out)

async def main():
    init_db()
    os.makedirs("downloads", exist_ok=True)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
