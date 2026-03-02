import asyncio, os, logging, re
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
URL_REGEX = re.compile(r'https?://\S+') # Ssilkalarni aniqlash uchun

class AdminState(StatesGroup):
    waiting_for_broadcast = State()

# --- YANGILANGAN VA KENGAYTIRILGAN MATNLAR (418-rasmdagidek) ---
def get_welcome_text(lang, bot_username):
    texts = {
        'uz': f"🔥 Assalomu alaykum. @{bot_username} ga Xush kelibsiz. Bot orqali quyidagilarni yuklab olishingiz mumkin:\n\n"
              f"• **Instagram** - post va IGTV + audio bilan;\n"
              f"• **TikTok** - suv belgisiz video + audio bilan;\n"
              f"• **YouTube** - Videolar va shorts + audio bilan;\n"
              f"• **Snapchat** - suv belgisiz video + audio bilan;\n"
              f"• **Likee** - suv belgisiz video + audio bilan;\n"
              f"• **Pinterest** - suv belgisiz video va rasmlar;\n"
              f"• **Threads** - video va rasmlar + audio bilan;\n\n"
              f"**Shazam funksiya:**\n"
              f"• Qo'shiq nomi yoki ijrochi ismi\n"
              f"• Qo'shiq matni\n"
              f"• Ovozli xabar\n"
              f"• Video\n"
              f"• Audio\n"
              f"• Video xabar\n\n"
              f"🚀 Yuklab olmoqchi bo'lgan videoga havolani yuboring!\n"
              f"😎 Bot guruhlarda ham ishlay oladi!",
              
        'kr': f"🔥 Ассалому алайкум. @{bot_username} га Хуш келибсиз. Бот орқали қуйидагиларни юклаб олишингиз мумкин:\n\n"
              f"• **Instagram** - пост ва IGTV + аудио билан;\n"
              f"• **TikTok** - сув белгисиз видео + аудио билан;\n"
              f"• **YouTube** - Видеолар ва шортс + аудио билан;\n"
              f"• **Snapchat** - сув белгисиз видео + аудио билан;\n"
              f"• **Likee** - сув белгисиз видео + аудио билан;\n"
              f"• **Pinterest** - сув белгисиз видео ва расмлар;\n"
              f"• **Threads** - видео ва расмлар + аудио билан;\n\n"
              f"**Шазам функцияси:**\n"
              f"• Қўшиқ номи ёки ижрочи исми\n"
              f"• Қўшиқ матни\n"
              f"• Овозли хабар\n"
              f"• Видео\n"
              f"• Аудио\n"
              f"• Видео хабар\n\n"
              f"🚀 Юклаб олмоқчи бўлган видеога ҳаволани юборинг!\n"
              f"😎 Бот гуруҳларда ҳам ишлай олади!",
              
        'ru': f"🔥 Здравствуйте! Добро пожаловать в @{bot_username}. Вы можете скачивать:\n\n"
              f"• Instagram, TikTok, YouTube, Snapchat, Likee, Pinterest, Threads (видео и аудио без водяных знаков).\n\n"
              f"**Функция Shazam:** распознает голосовые, видео, аудио сообщения и находит тексты песен.\n\n"
              f"🚀 Отправьте ссылку на видео для скачивания!",
              
        'en': f"🔥 Hello! Welcome to @{bot_username}. You can download from:\n\n"
              f"• Instagram, TikTok, YouTube, Snapchat, Likee, Pinterest, Threads (watermark-free).\n\n"
              f"**Shazam Feature:** recognizes voice, video, audio, and finds lyrics.\n\n"
              f"🚀 Send a link to download!"
    }
    return texts.get(lang, texts['uz'])

def lang_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇿 O'zbekcha", callback_data="lang_uz")
    builder.button(text="🇺🇿 Ўзбекча", callback_data="lang_kr")
    builder.button(text="🇷🇺 Русский", callback_data="lang_ru")
    builder.button(text="🇬🇧 English", callback_data="lang_en")
    builder.adjust(2)
    return builder.as_markup()

def get_start_group_kb(bot_username):
    builder = InlineKeyboardBuilder()
    builder.button(text="Guruhga qo'shish ↩️", url=f"https://t.me/{bot_username}?startgroup=true")
    return builder.as_markup()

# MUSIQA TUGMALARI (Avvalgidek tartibli)
def get_search_keyboard(user_id, page=0):
    results = USER_SEARCHES.get(user_id, {}).get('results', [])
    total_pages = (len(results) + 5) // 6
    builder = InlineKeyboardBuilder()
    start, end = page * 6, (page + 1) * 6
    for i, _ in enumerate(results[start:end]):
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
    builder.button(text="📝 Matn", callback_data=f"ly_{q_key}")
    builder.button(text="🎛 Effektlar", callback_data=f"effmenu_{q_key}")
    builder.button(text="💔 Olib tashlash" if q_key in favs else "❤️ Saqlash", callback_data=f"fv_{q_key}")
    builder.button(text="➕ Guruhga qo'shish", url=f"https://t.me/{bot_name}?startgroup=true")
    builder.adjust(2, 1, 1) 
    return builder.as_markup()

def get_effects_kb(q_key):
    builder = InlineKeyboardBuilder()
    builder.button(text="🎧 8D", callback_data=f"8d_{q_key}")
    builder.button(text="🏟 Hall", callback_data=f"ch_{q_key}")
    builder.button(text="🐢 Slow", callback_data=f"sl_{q_key}")
    builder.button(text="🔙 Orqaga", callback_data=f"back_{q_key}")
    builder.adjust(2, 1, 1)
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
        b = await bot.get_me()
        await m.answer(get_welcome_text(lang, b.username), reply_markup=get_start_group_kb(b.username))

@dp.callback_query(F.data.startswith("lang_"))
async def set_user_lang(c: CallbackQuery):
    lang = c.data.split("_")[1]
    set_lang(c.from_user.id, lang)
    b = await bot.get_me()
    await c.message.edit_text(get_welcome_text(lang, b.username), reply_markup=get_start_group_kb(b.username))

@dp.message(Command("admin"))
async def admin(m: types.Message):
    if m.from_user.id != ADMIN_ID: return
    u, c = get_stats(); today_dl = get_daily_downloads()
    kb = InlineKeyboardBuilder().button(text="📢 Xabar yuborish", callback_data="bc").as_markup()
    await m.answer(f"👮‍♂️ **Admin Panel**\n\n👥 Jami a'zolar: {u}\n🎵 Baza: {c}\n📈 Bugun yuklandi: {today_dl}", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "bc")
async def bc(c: CallbackQuery, s: FSMContext):
    await c.message.answer("Tarqatmoqchi bo'lgan xabaringizni yuboring:"); await s.set_state(AdminState.waiting_for_broadcast)

@dp.message(AdminState.waiting_for_broadcast)
async def bc_p(m: types.Message, s: FSMContext):
    for u in get_all_users():
        try: await m.copy_to(u); await asyncio.sleep(0.05)
        except: pass
    await m.answer("✅ Xabar yuborildi!"); await s.clear()

# --- YANGI: BARCHA MEDIA VA SSILKALARNI QABUL QILISH ---
@dp.message(F.text | F.voice | F.audio | F.video | F.video_note)
async def handle_all_types(m: types.Message, state: FSMContext):
    if await state.get_state() == AdminState.waiting_for_broadcast.state: return
    if m.text and m.text.startswith("/"): return
    lang = get_lang(m.from_user.id) or 'uz'
    
    # 1. AGAR SSILKA (LINK) BO'LSA - VIDEO YUKLAYDI
    if m.text and URL_REGEX.match(m.text):
        msg = await m.answer("⏳ Video yuklanmoqda. Iltimos, kuting...")
        try:
            temp_path = f"downloads/{m.from_user.id}_vid"
            file_path, title = download_universal_video(m.text, temp_path)
            b = await bot.get_me()
            await bot.send_video(m.from_user.id, FSInputFile(file_path), caption=f"🎥 {title}\n🤖 @{b.username}")
            os.remove(file_path)
            increment_daily_download()
            return await msg.delete()
        except Exception as e:
            return await msg.edit_text("❌ Ssilka orqali videoni yuklab bo'lmadi yoki yopiq profil.")
            
    # 2. AGAR MEDIA (OVOZ, VIDEO, KРУЖОК) BO'LSA - SHAZAM ISHLAYDI
    if m.voice or m.audio or m.video or m.video_note:
        msg = await m.answer("🎵 Shazam ishga tushdi, musiqa aniqlanmoqda...")
        # Qaysi turdagi faylligini aniqlab ID sini olish
        if m.voice: file_id = m.voice.file_id
        elif m.audio: file_id = m.audio.file_id
        elif m.video: file_id = m.video.file_id
        else: file_id = m.video_note.file_id
        
        file = await bot.get_file(file_id)
        temp_path = f"downloads/{file_id}.ext"
        await bot.download_file(file.file_path, destination=temp_path)
        
        query = await recognize_song(temp_path)
        os.remove(temp_path)
        if not query: return await msg.edit_text("❌ Qanday musiqa ekanligini aniqlay olmadim.")
        await msg.edit_text("🔍 " + ("Qidirilmoqda..." if lang == 'uz' else "Поиск..."))
    else: 
        # 3. AGAR ODDIY MATN BO'LSA - QO'SHIQ QIDIRADI
        query = m.text
        msg = await m.answer("🔍 Qidirilmoqda..." if lang == 'uz' else "🔍 Поиск...")
        
    res = search_combined(query) 
    if not res: return await msg.edit_text("❌ Topilmadi." if lang == 'uz' else "❌ Не найдено.")
    
    USER_SEARCHES[m.from_user.id] = {'results': res, 'query': query, 'page': 0}
    await send_p(m.from_user.id, 0, msg)

async def send_p(uid, p, msg):
    d = USER_SEARCHES[uid]; r = d['results'][p*6:(p+1)*6]
    t = f"🔍 **{d['query']}** natijalari (Jami: {len(d['results'])} ta):\n\n"
    for i, x in enumerate(r): t += f"**{i+1}.** {x['title']}\n"
    await msg.edit_text(t + "\nIltimos, o'zingizga kerakli variantni tanlang 👇\n*(Ko'proq ko'rish uchun ➡️ bosing)*", reply_markup=get_search_keyboard(uid, p), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("p_"))
async def p_nav(c: CallbackQuery):
    p = int(c.data.split("_")[1]); await send_p(c.from_user.id, p, c.message)

@dp.callback_query(F.data.startswith("dl_"))
async def dl(c: CallbackQuery):
    idx = int(c.data.split("_")[1]); d = USER_SEARCHES[c.from_user.id]['results'][idx]
    q_key = "".join(x for x in d['title'][:15] if x.isalnum()).lower()
    await c.message.edit_text(f"⏳ **{d['title']}** yuklanmoqda..."); b = await bot.get_me()
    
    cached = get_cache(q_key); cap = f"🎧 Musiqa: {d['title']}\n\n🤖 @{b.username}"
    
    if cached:
        await bot.send_audio(c.from_user.id, cached, caption=cap, reply_markup=get_actions_kb(q_key, c.from_user.id, b.username))
    else:
        f = download_music(d['url'], f"downloads/{q_key}")
        sent = await bot.send_audio(c.from_user.id, FSInputFile(f), caption=cap, reply_markup=get_actions_kb(q_key, c.from_user.id, b.username))
        add_cache(q_key, sent.audio.file_id, d['title']); os.remove(f)
    increment_daily_download()
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

@dp.callback_query(F.data.startswith("effmenu_"))
async def open_effects(c: CallbackQuery):
    q_key = c.data.replace("effmenu_", "")
    await c.message.edit_reply_markup(reply_markup=get_effects_kb(q_key))

@dp.callback_query(F.data.startswith("back_"))
async def close_effects(c: CallbackQuery):
    q_key = c.data.replace("back_", ""); b = await bot.get_me()
    await c.message.edit_reply_markup(reply_markup=get_actions_kb(q_key, c.from_user.id, b.username))

@dp.callback_query(F.data.startswith(("8d_", "sl_", "ch_", "ly_")))
async def effects(c: CallbackQuery):
    act, q_key = c.data.split("_", 1); await c.answer("⏳ Jarayonda..."); b = await bot.get_me()
    
    if act == "ly":
        query_for_lyrics = q_key 
        lyrics_text = get_lyrics_text(query_for_lyrics)
        return await c.message.reply(f"📝 **Qo'shiq matni:**\n\n{lyrics_text[:4000]}", parse_mode="Markdown")
    
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
    init_db(); os.makedirs("downloads", exist_ok=True)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
