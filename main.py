import asyncio, os, logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

# O'zimiz yaratgan fayllardan barcha asboblarni chaqirib olamiz
from database import *
from music_api import *
from audio_processor import *

# Sozlamalarni yuklash (Token va Admin ID)
load_dotenv()
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# Foydalanuvchilarning qidiruv natijalarini vaqtincha saqlab turuvchi xotira
USER_SEARCHES = {}

# Admin xabar yuborayotgan holatni aniqlash uchun
class AdminState(StatesGroup):
    waiting_for_broadcast = State()

# --- 1. TILLAR VA MATNLAR ---
LANGS = {
    'uz': {'welcome': "👋 Salom! Musiqa nomini yozing ёки ovoz yuboring.", 'search': "🔍 Qidirilmoqda...", 'not_found': "❌ Afsuski, topilmadi."},
    'kr': {'welcome': "👋 Салом! Мусиқа номини ёзинг ёки овоз юборинг.", 'search': "🔍 Қидирилмоқда...", 'not_found': "❌ Афсуски, топилмади."},
    'ru': {'welcome': "👋 Привет! Напишите название музыки или отправьте голосовое.", 'search': "🔍 Поиск...", 'not_found': "❌ Не найдено."},
    'en': {'welcome': "👋 Hello! Send a song name or voice message.", 'search': "🔍 Searching...", 'not_found': "❌ Not found."}
}

def lang_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇿 O'zbekcha", callback_data="lang_uz")
    builder.button(text="🇺🇿 Ўзбекча", callback_data="lang_kr")
    builder.button(text="🇷🇺 Русский", callback_data="lang_ru")
    builder.button(text="🇬🇧 English", callback_data="lang_en")
    builder.adjust(2) # 2 tadan 2 qator
    return builder.as_markup()

# --- 2. QIDIRUV TUGMALARI (1 dan 6 gacha va Sahifalash) ---
def get_search_keyboard(user_id, page=0):
    results = USER_SEARCHES.get(user_id, {}).get('results', [])
    total_pages = (len(results) + 5) // 6
    builder = InlineKeyboardBuilder()
    
    start, end = page * 6, (page + 1) * 6
    current_results = results[start:end]
    
    for i, _ in enumerate(current_results):
        builder.button(text=str(i+1), callback_data=f"dl_{start+i}")
    
    builder.adjust(5, 1) # 5 ta tepada, 6-chi pastda
    
    # ⬅️ ❌ ➡️ tugmalari
    builder.row(
        types.InlineKeyboardButton(text="⬅️", callback_data=f"p_{page-1}" if page > 0 else "noop"),
        types.InlineKeyboardButton(text="❌", callback_data="del"),
        types.InlineKeyboardButton(text="➡️", callback_data=f"p_{page+1}" if page < total_pages - 1 else "noop")
    )
    return builder.as_markup()

# --- 3. MUSIQA OSTIDAGI EFFEKTLAR VA GURUHGA QO'SHISH ---
def get_actions_kb(q_key, user_id, bot_name):
    favs = get_favorites(user_id)
    builder = InlineKeyboardBuilder()
    builder.button(text="🎧 8D", callback_data=f"8d_{q_key}")
    builder.button(text="🏟 Concert Hall", callback_data=f"ch_{q_key}")
    builder.button(text="🐢 Slowed", callback_data=f"sl_{q_key}")
    builder.button(text="📝 Tekst", callback_data=f"ly_{q_key}")
    builder.button(text="💔 Olib tashlash" if q_key in favs else "❤️ Saqlash", callback_data=f"fv_{q_key}")
    builder.button(text="➕ Guruhga qo'shish", url=f"https://t.me/{bot_name}?startgroup=true")
    builder.adjust(2, 1, 2, 1) # Tugmalarni qatorlarga taxlash
    return builder.as_markup()

# --- 4. START VA ADMINGA XABAR BERSH ---
@dp.message(Command("start"))
async def start(m: types.Message):
    # Foydalanuvchini bazaga qo'shish va u yangimi yo'qmi tekshirish
    is_new = add_user(m.from_user.id)
    
    # Faqat yangi kirgan bo'lsa, adminga xabar ketadi
    if is_new and ADMIN_ID != 0:
        try:
            await bot.send_message(chat_id=ADMIN_ID, text="🎉 Yangi obunachi qo'shildi!")
        except: pass

    # Tilni so'rash yoki salom berish
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

# --- 5. ADMIN PANEL ---
@dp.message(Command("admin"))
async def admin(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    u, c = get_stats()
    kb = InlineKeyboardBuilder().button(text="📢 Xabar yuborish", callback_data="bc").as_markup()
    await m.answer(f"👮‍♂️ **Admin Panel**\n👥 A'zolar: {u}\n🎵 Baza: {c}", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "bc")
async def bc(c: CallbackQuery, s: FSMContext):
    await c.message.answer("Tarqatmoqchi bo'lgan xabaringizni yuboring:"); await s.set_state(AdminState.waiting_for_broadcast)

@dp.message(AdminState.waiting_for_broadcast)
async def bc_p(m: types.Message, s: FSMContext):
    for u in get_all_users():
        try: await m.copy_to(u); await asyncio.sleep(0.05)
        except: pass
    await m.answer("✅ Xabar barchaga yuborildi!"); await s.clear()

# --- 6. MUSIQA QIDIRISH ---
@dp.message(F.text)
async def search(m: types.Message, state: FSMContext):
    if await state.get_state() == AdminState.waiting_for_broadcast.state or m.text.startswith("/"): return
    lang = get_lang(m.from_user.id) or 'uz'
    query = m.text
    msg = await m.answer(LANGS[lang]['search'])
    
    res = search_combined(query) # music_api.py dagi funksiya ishga tushadi
    
    if not res: return await msg.edit_text(LANGS[lang]['not_found'])
    USER_SEARCHES[m.from_user.id] = {'results': res, 'query': query, 'page': 0, 'lang': lang}
    await send_p(m.from_user.id, 0, msg)

async def send_p(uid, p, msg):
    d = USER_SEARCHES[uid]; r = d['results'][p*6:(p+1)*6]
    t = f"🔍 **{d['query']}** natijalari:\n\n"
    for i, x in enumerate(r): t += f"**{i+1}.** {x['title']}\n"
    await msg.edit_text(t + "\nIltimos, o'zingizga kerakli variantni tanlang 👇", reply_markup=get_search_keyboard(uid, p), parse_mode="Markdown")

# Sahifalarni o'tkazish (⬅️ ➡️ tugmalari uchun)
@dp.callback_query(F.data.startswith("p_"))
async def p_nav(c: CallbackQuery):
    p = int(c.data.split("_")[1]); await send_p(c.from_user.id, p, c.message)

# --- 7. MUSIQANI YUKLASH (KESH YOKI INTERNETDAN) ---
@dp.callback_query(F.data.startswith("dl_"))
async def dl(c: CallbackQuery):
    idx = int(c.data.split("_")[1]); d = USER_SEARCHES[c.from_user.id]['results'][idx]
    q_key = "".join(x for x in d['title'][:15] if x.isalnum()).lower()
    await c.message.edit_text(f"⏳ **{d['title']}** yuklanmoqda..."); b = await bot.get_me()
    
    cached = get_cache(q_key) # Bazada bormi yo'qmi tekshiradi
    cap = f"🎧 Musiqa: {d['title']}\n\n🤖 @{b.username} orqali istagan musiqangizni tez va oson toping!🚀"
    
    if cached: # Agar oldin yuklangan bo'lsa tezda bazadan beradi
        await bot.send_audio(c.from_user.id, cached, caption=cap, reply_markup=get_actions_kb(q_key, c.from_user.id, b.username))
    else: # Yo'q bo'lsa Yandex yoki YouTube'dan tortib oladi
        f = download_music(d['url'], f"downloads/{q_key}")
        sent = await bot.send_audio(c.from_user.id, FSInputFile(f), caption=cap, reply_markup=get_actions_kb(q_key, c.from_user.id, b.username))
        add_cache(q_key, sent.audio.file_id, d['title']) # Xotiraga mitti ID ni saqlaydi
        os.remove(f) # Va qattiq faylni darhol o'chirib tashlaydi (server to'lmaydi)
    await c.message.delete()

# --- 8. YORDAMCHI TUGMALAR (X va Saqlash) ---
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

# --- 9. EFFEKTLAR VA MATN ---
@dp.callback_query(F.data.startswith(("8d_", "sl_", "ch_", "ly_")))
async def effects(c: CallbackQuery):
    act, q_key = c.data.split("_", 1); await c.answer("⏳ Jarayonda..."); b = await bot.get_me()
    
    if act == "ly":
        return await c.message.reply("📝 Qo'shiq matnlarini topish funksiyasi tez orada to'liq ishga tushadi!", parse_mode="Markdown")

    f_id = get_cache(f"orig_{q_key}") or get_cache(q_key)
    if not f_id: return
    file = await bot.get_file(f_id); tmp, out = f"downloads/t_{q_key}.mp3", f"downloads/{act}_{q_key}.mp3"
    
    await bot.download_file(file.file_path, tmp) # Musiqani vaqtincha oladi
    # Tegishli effektni qo'llaydi
    if act == "8d": make_8d(tmp, out)
    elif act == "sl": make_slowed(tmp, out)
    elif act == "ch": make_concert_hall(tmp, out)
    
    await bot.send_audio(c.from_user.id, FSInputFile(out), caption=f"✨ Effekt: {act.upper()}\n🤖 @{b.username}")
    os.remove(tmp); os.remove(out) # Yana joyni tozalab tashlaydi

# --- 10. BOTNI ISHGA TUSHIRISH ---
async def main():
    init_db() # Bazani yaratadi
    os.makedirs("downloads", exist_ok=True) # Papka ochadi
    await dp.start_polling(bot) # Botni yurgizadi

if __name__ == "__main__":
    asyncio.run(main())
