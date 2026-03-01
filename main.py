import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile, InlineQuery, InlineQueryResultCachedAudio
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

from database import init_db, add_user, get_lang, set_lang, get_cache, add_cache, get_all_users, get_stats, get_top_music, toggle_favorite, get_favorites, search_cache_inline
from texts import LANGS
from music_api import recognize_song, download_music, get_lyrics, search_track_list
from audio_processor import make_8d, make_slowed, make_concert_hall

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_URL = os.getenv("CHANNEL_URL")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

os.makedirs("downloads", exist_ok=True)
USER_SEARCHES = {}

class AdminState(StatesGroup):
    waiting_for_broadcast = State()

async def check_sub(user_id):
    if not CHANNEL_ID or not CHANNEL_URL: return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status not in ['left', 'kicked']
    except: return True

def lang_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇿 O'zbekcha", callback_data="lang_uz")
    builder.button(text="🇷🇺 Русский", callback_data="lang_ru")
    builder.adjust(2)
    return builder.as_markup()

def get_search_keyboard(user_id, page=0):
    data = USER_SEARCHES.get(user_id, {})
    results = data.get('results', [])
    total_pages = (len(results) + 5) // 6 
    
    builder = InlineKeyboardBuilder()
    start = page * 6
    end = start + 6
    current_results = results[start:end]
    
    for i, _ in enumerate(current_results):
        builder.button(text=str(i+1), callback_data=f"dl_{start+i}")
        
    builder.button(text="⬅️", callback_data=f"page_{page-1}" if page > 0 else "noop")
    builder.button(text="❌", callback_data="del_msg")
    builder.button(text="➡️", callback_data=f"page_{page+1}" if page < total_pages - 1 else "noop")
    
    num_len = len(current_results)
    if num_len <= 5:
        builder.adjust(num_len, 3)
    else:
        builder.adjust(5, num_len - 5, 3) 
        
    return builder.as_markup()

# --- TUGMALAR (Guruhga qo'shish shu yerda) ---
def music_actions_keyboard(query_key, user_id, bot_username):
    favs = get_favorites(user_id)
    is_fav = query_key in favs
    builder = InlineKeyboardBuilder()
    
    builder.button(text="🎧 8D", callback_data=f"8d_{query_key}")
    builder.button(text="🏟 Concert Hall", callback_data=f"ch_{query_key}")
    builder.button(text="🐢 Slowed", callback_data=f"sl_{query_key}")
    
    builder.button(text="📝 Tekst", callback_data=f"ly_{query_key}")
    fav_text = "💔 Olib tashlash" if is_fav else "❤️ Saqlash"
    builder.button(text=fav_text, callback_data=f"fv_{query_key}")
    
    # YANGI: Guruhga qo'shish tugmasi
    builder.button(text="➕ Guruhga qo'shish", url=f"https://t.me/{bot_username}?startgroup=true")
    
    # Qatorlarni taxlaymiz: 2 ta, 1 ta, 2 ta, 1 ta
    builder.adjust(2, 1, 2, 1)
    return builder.as_markup()

@dp.callback_query(F.data == "noop")
async def noop_handler(callback: types.CallbackQuery):
    await callback.answer()

@dp.callback_query(F.data == "del_msg")
async def del_msg_handler(callback: types.CallbackQuery):
    await callback.message.delete()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    add_user(message.from_user.id)
    lang = get_lang(message.from_user.id)
    if not lang: await message.answer(LANGS['uz']['choose_lang'], reply_markup=lang_keyboard())
    else: await message.answer(LANGS[lang]['welcome'])

@dp.callback_query(F.data == "check_sub")
async def check_sub_handler(callback: types.CallbackQuery):
    if await check_sub(callback.from_user.id):
        await callback.message.delete()
        await callback.answer("✅ Rahmat!", show_alert=True)
    else:
        await callback.answer("❌ Hali kanalga a'zo bo'lmadingiz!", show_alert=True)

@dp.callback_query(F.data.startswith("lang_"))
async def process_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    set_lang(callback.from_user.id, lang)
    await callback.message.edit_text(LANGS[lang]['welcome'])

@dp.message(F.text | F.voice | F.audio)
async def handle_search(message: types.Message, state: FSMContext):
    if await state.get_state() == AdminState.waiting_for_broadcast.state: return
    user_id = message.from_user.id
    if not await check_sub(user_id):
        btn = InlineKeyboardBuilder()
        btn.button(text="📢 Kanalga a'zo bo'lish", url=CHANNEL_URL)
        btn.button(text="✅ Tasdiqlash", callback_data="check_sub")
        return await message.answer("⚠️ Botdan foydalanish uchun kanalimizga a'zo bo'ling!", reply_markup=btn.as_markup())

    lang = get_lang(user_id) or 'uz'
    msg = await message.answer(LANGS[lang]['search_start'])
    
    if message.voice or message.audio:
        file_id = message.voice.file_id if message.voice else message.audio.file_id
        file = await bot.get_file(file_id)
        temp_path = f"downloads/{file_id}.ogg"
        await bot.download_file(file.file_path, destination=temp_path)
        query = await recognize_song(temp_path)
        os.remove(temp_path)
        if not query: return await msg.edit_text(LANGS[lang]['not_found'])
        await process_download(user_id, query, query, msg, lang)
    else:
        query = message.text
        results = search_track_list(query, limit=30)
        if not results: return await msg.edit_text(LANGS[lang]['not_found'])
            
        USER_SEARCHES[user_id] = {'query': query, 'results': results, 'page': 0}
        await send_search_page(user_id, 0, msg, query)

async def send_search_page(user_id, page, msg, query):
    results = USER_SEARCHES[user_id]['results']
    start = page * 6
    end = start + 6
    
    text = f"🔍 **{query}** natijalari:\n\n"
    for i, res in enumerate(results[start:end]):
        text += f"**{i+1}.** {res['title']}\n"
        
    await msg.edit_text(text, reply_markup=get_search_keyboard(user_id, page), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("page_"))
async def handle_pagination(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    USER_SEARCHES[user_id]['page'] = page
    query = USER_SEARCHES[user_id]['query']
    await send_search_page(user_id, page, callback.message, query)

@dp.callback_query(F.data.startswith("dl_"))
async def handle_download_selection(callback: types.CallbackQuery):
    index = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    lang = get_lang(user_id) or 'uz'
    
    if user_id not in USER_SEARCHES or len(USER_SEARCHES[user_id].get('results', [])) <= index:
        return await callback.answer("❌ Qidiruv eskirgan.", show_alert=True)
        
    selected_track = USER_SEARCHES[user_id]['results'][index]
    await callback.message.edit_text(f"⏳ **{selected_track['title']}** yuklanmoqda...", parse_mode="Markdown")
    await process_download(user_id, selected_track['title'], selected_track['url'], callback.message, lang)

async def process_download(user_id, title, url_or_query, msg, lang):
    query_key = title[:20].strip().replace("/", "").replace("\\", "")
    cached_id = get_cache(f"orig_{query_key}")
    bot_info = await bot.get_me()
    
    # Chiroyli caption (reklama matni)
    caption_text = f"🎧 Musiqa: {title}\n\n🤖 Bot: @{bot_info.username}\n🚀 Eng sara musiqalar bizning botda!"
    
    if cached_id:
        await bot.send_audio(chat_id=user_id, audio=cached_id, caption=caption_text, reply_markup=music_actions_keyboard(query_key, user_id, bot_info.username))
        await msg.delete()
    else:
        try:
            download_path = f"downloads/{query_key}"
            final_mp3 = download_music(url_or_query, download_path)
            sent_audio = await bot.send_audio(
                chat_id=user_id, 
                audio=FSInputFile(final_mp3),
                caption=caption_text,
                reply_markup=music_actions_keyboard(query_key, user_id, bot_info.username)
            )
            add_cache(f"orig_{query_key}", sent_audio.audio.file_id)
            os.remove(final_mp3)
            await msg.delete()
        except Exception as e:
            await msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")

@dp.callback_query(F.data.startswith(("ly_", "8d_", "sl_", "ch_")))
async def handle_music_actions(callback: types.CallbackQuery):
    action, query_key = callback.data.split("_", 1)
    user_id = callback.from_user.id
    if action == "ly":
        lyrics = get_lyrics(query_key)
        await callback.message.reply(f"📝 **Matn:**\n\n{lyrics[:4000]}", parse_mode="Markdown")
        return await callback.answer()

    cache_key = f"{action}_{query_key}"
    cached_effect_id = get_cache(cache_key)
    bot_info = await bot.get_me()
    
    clean_name = query_key.replace("orig_", "").capitalize()
    caption_text = f"🎧 Musiqa: {clean_name} ({action.upper()})\n\n🤖 Bot: @{bot_info.username}\n🚀 Eng sara musiqalar bizning botda!"

    if cached_effect_id:
        await bot.send_audio(chat_id=user_id, audio=cached_effect_id, caption=caption_text)
        return await callback.answer()

    orig_file_id = get_cache(f"orig_{query_key}")
    if not orig_file_id: return await callback.answer("❌ Original fayl yo'q.", show_alert=True)

    await callback.answer("⏳ Effekt qo'shilmoqda, biroz kuting...")
    file = await bot.get_file(orig_file_id)
    temp_orig = f"downloads/temp_{query_key}.mp3"
    temp_effect = f"downloads/{action}_{query_key}.mp3"
    
    await bot.download_file(file.file_path, destination=temp_orig)
    if action == "8d": make_8d(temp_orig, temp_effect)
    elif action == "sl": make_slowed(temp_orig, temp_effect)
    elif action == "ch": make_concert_hall(temp_orig, temp_effect)
        
    sent_effect = await bot.send_audio(chat_id=user_id, audio=FSInputFile(temp_effect), caption=caption_text)
    add_cache(cache_key, sent_effect.audio.file_id)
    os.remove(temp_orig)
    os.remove(temp_effect)

@dp.inline_query()
async def inline_search(inline_query: InlineQuery):
    query = inline_query.query or ""
    results = search_cache_inline(query)
    inline_results = []
    bot_info = await bot.get_me()
    for idx, (q_key, f_id) in enumerate(results):
        clean_name = q_key.replace("orig_", "").capitalize()
        inline_results.append(InlineQueryResultCachedAudio(id=str(idx), audio_file_id=f_id, caption=f"🎵 {clean_name}\n🤖 @{bot_info.username}"))
    await inline_query.answer(inline_results, is_personal=False, cache_time=10)

@dp.message(Command("fav"))
async def cmd_fav(message: types.Message):
    favs = get_favorites(message.from_user.id)
    if not favs: return await message.answer("Sizda hali saqlangan musiqalar yo'q.")
    text = "❤️ **Sizning sevimli musiqalaringiz:**\n\n"
    builder = InlineKeyboardBuilder()
    for i, q_key in enumerate(favs):
        text += f"{i+1}. {q_key.capitalize()}\n"
        builder.button(text=f"{i+1} ⬇️", callback_data=f"dlfav_{q_key}")
    builder.adjust(5)
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("dlfav_"))
async def dl_fav(callback: types.CallbackQuery):
    q_key = callback.data.replace("dlfav_", "")
    file_id = get_cache(f"orig_{q_key}")
    bot_info = await bot.get_me()
    
    caption_text = f"🎧 Musiqa: {q_key.capitalize()}\n\n🤖 Bot: @{bot_info.username}\n🚀 Eng sara musiqalar bizning botda!"
    
    if file_id: await bot.send_audio(callback.from_user.id, audio=file_id, caption=caption_text, reply_markup=music_actions_keyboard(q_key, callback.from_user.id, bot_info.username))
    await callback.answer()

@dp.callback_query(F.data.startswith("fv_"))
async def handle_favorite(callback: types.CallbackQuery):
    query_key = callback.data.replace("fv_", "")
    is_now_fav = toggle_favorite(callback.from_user.id, query_key)
    bot_info = await bot.get_me()
    
    if is_now_fav: await callback.answer("❤️ Sevimlilarga qo'shildi!", show_alert=True)
    else: await callback.answer("💔 Olib tashlandi!", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=music_actions_keyboard(query_key, callback.from_user.id, bot_info.username))

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    u_count, c_count = get_stats()
    text = f"👮‍♂️ **Admin Panel**\n\n👥 A'zolar: {u_count} ta\n🎵 Musiqalar: {c_count} ta"
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Xabar yuborish", callback_data="admin_broadcast")
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("📝 Xabaringizni yozing:")
    await state.set_state(AdminState.waiting_for_broadcast)
    await callback.answer()

@dp.message(AdminState.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    users = get_all_users()
    count = 0
    await message.answer(f"⏳ Xabar yuborilmoqda...")
    for user in users:
        try:
            await message.copy_to(user)
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    await message.answer(f"✅ Xabar {count} kishiga yetib bordi!")
    await state.clear()

@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    tops = get_top_music(10)
    if not tops: return await message.answer("Bazada musiqa yo'q.")
    text = "🔥 **Top 10 musiqa:**\n\n"
    builder = InlineKeyboardBuilder()
    for i, (q_key, count) in enumerate(tops):
        clean_name = q_key.replace("orig_", "").capitalize()
        text += f"{i+1}. {clean_name} ({count} marta)\n"
        builder.button(text=f"{i+1} ⬇️", callback_data=f"dltop_{q_key}")
    builder.adjust(5)
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("dltop_"))
async def download_top(callback: types.CallbackQuery):
    q_key = callback.data.replace("dltop_", "")
    file_id = get_cache(q_key)
    bot_info = await bot.get_me()
    clean_name = q_key.replace("orig_", "")
    
    caption_text = f"🎧 Musiqa: {clean_name.capitalize()}\n\n🤖 Bot: @{bot_info.username}\n🚀 Eng sara musiqalar bizning botda!"
    
    if file_id:
        await bot.send_audio(callback.from_user.id, audio=file_id, caption=caption_text, reply_markup=music_actions_keyboard(clean_name, callback.from_user.id, bot_info.username))
    await callback.answer()

async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
