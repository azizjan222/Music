import asyncio, os, logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile
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

def get_actions_kb(q_key, user_id, bot_name):
    favs = get_favorites(user_id)
    builder = InlineKeyboardBuilder()
    builder.button(text="🎧 8D", callback_data=f"8d_{q_key}")
    builder.button(text="🏟 Hall", callback_data=f"ch_{q_key}")
    builder.button(text="🐢 Slow", callback_data=f"sl_{q_key}")
    builder.button(text="💔 Olib tashlash" if q_key in favs else "❤️ Saqlash", callback_data=f"fv_{q_key}")
    builder.button(text="➕ Guruhga qo'shish", url=f"https://t.me/{bot_name}?startgroup=true")
    builder.adjust(3, 1, 1)
    return builder.as_markup()

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    u, c = get_stats()
    builder = InlineKeyboardBuilder().button(text="📢 Xabar yuborish", callback_data="admin_broadcast")
    await message.answer(f"👮‍♂️ Admin\n👥 A'zolar: {u}\n🎵 Baza: {c}", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Xabarni yozing:"); await state.set_state(AdminState.waiting_for_broadcast)

@dp.message(AdminState.waiting_for_broadcast)
async def broadcast_process(message: types.Message, state: FSMContext):
    for u in get_all_users():
        try: await message.copy_to(u); await asyncio.sleep(0.05)
        except: pass
    await message.answer("✅ Yuborildi"); await state.clear()

@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    tops = get_top_songs()
    if not tops: return await message.answer("Hali top musiqalar yo'q.")
    text = "🔥 Haftalik Top:\n\n"; builder = InlineKeyboardBuilder()
    for i, (title, q_key) in enumerate(tops):
        text += f"{i+1}. {title}\n"; builder.button(text=str(i+1), callback_data=f"dl_top_{q_key}")
    builder.adjust(5); await message.answer(text, reply_markup=builder.as_markup())

@dp.message(F.text)
async def handle_search(message: types.Message, state: FSMContext):
    if await state.get_state() == AdminState.waiting_for_broadcast.state or message.text.startswith("/"): return
    query = message.text; msg = await message.answer("🔍 Qidirilmoqda..."); results = search_combined(query)
    if not results: return await msg.edit_text("❌ Topilmadi.")
    USER_SEARCHES[message.from_user.id] = {'results': results}
    text = f"🎵 **{query}** natijalari:\n\n"; builder = InlineKeyboardBuilder()
    for i, res in enumerate(results[:6]):
        text += f"**{i+1}.** {res['title']}\n"; builder.button(text=str(i+1), callback_data=f"dl_{i}")
    builder.adjust(6); await msg.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("dl_"))
async def handle_dl(callback: types.CallbackQuery):
    idx = int(callback.data.split("_")[1]); user_id = callback.from_user.id
    selected = USER_SEARCHES[user_id]['results'][idx]
    q_key = "".join(x for x in selected['title'][:15] if x.isalnum()).lower()
    
    cached = get_cache(q_key)
    bot_info = await bot.get_me()
    caption = f"🎧 {selected['title']}\n🤖 @{bot_info.username}"
    
    if cached:
        await bot.send_audio(user_id, cached, caption=caption, reply_markup=get_actions_kb(q_key, user_id, bot_info.username))
    else:
        path = download_music(selected['url'], f"downloads/{q_key}")
        sent = await bot.send_audio(user_id, FSInputFile(path), caption=caption, reply_markup=get_actions_kb(q_key, user_id, bot_info.username))
        add_cache(q_key, sent.audio.file_id, selected['title']); os.remove(path)
    await callback.message.delete()

async def main():
    init_db(); os.makedirs("downloads", exist_ok=True); await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
