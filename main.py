import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import FSInputFile

from database import init_db, add_user, get_lang, set_lang, get_cache, add_cache
from texts import LANGS
from music_api import recognize_song, download_music, get_lyrics
from audio_processor import make_8d, make_slowed

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

os.makedirs("downloads", exist_ok=True)

def lang_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇿 O'zbekcha", callback_data="lang_uz")
    builder.button(text="🇺🇿 Ўзбекча", callback_data="lang_kr")
    builder.button(text="🇷🇺 Русский", callback_data="lang_ru")
    builder.button(text="🇬🇧 English", callback_data="lang_en")
    builder.adjust(2)
    return builder.as_markup()

def music_actions_keyboard(query_key):
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Tekst", callback_data=f"ly_{query_key}")
    builder.button(text="🎧 8D", callback_data=f"8d_{query_key}")
    builder.button(text="🐢 Slowed", callback_data=f"sl_{query_key}")
    builder.adjust(3)
    return builder.as_markup()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    add_user(message.from_user.id)
    lang = get_lang(message.from_user.id)
    if not lang:
        await message.answer(LANGS['uz']['choose_lang'], reply_markup=lang_keyboard())
    else:
        await message.answer(LANGS[lang]['welcome'])

@dp.callback_query(F.data.startswith("lang_"))
async def process_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    set_lang(callback.from_user.id, lang)
    await callback.message.edit_text(LANGS[lang]['welcome'])

@dp.message(F.text | F.voice | F.audio)
async def handle_search(message: types.Message):
    user_id = message.from_user.id
    lang = get_lang(user_id) or 'uz'
    msg = await message.answer(LANGS[lang]['search_start'])
    
    query = ""
    if message.voice or message.audio:
        file_id = message.voice.file_id if message.voice else message.audio.file_id
        file = await bot.get_file(file_id)
        temp_path = f"downloads/{file_id}.ogg"
        await bot.download_file(file.file_path, destination=temp_path)
        
        query = await recognize_song(temp_path)
        os.remove(temp_path)
        
        if not query:
            return await msg.edit_text(LANGS[lang]['not_found'])
    else:
        query = message.text

    query_key = query[:20].strip()
    cached_id = get_cache(f"orig_{query_key}")
    
    if cached_id:
        await bot.send_audio(chat_id=user_id, audio=cached_id, reply_markup=music_actions_keyboard(query_key))
        await msg.delete()
    else:
        try:
            download_path = f"downloads/{query_key}"
            final_mp3 = download_music(query, download_path)
            
            sent_audio = await bot.send_audio(
                chat_id=user_id, 
                audio=FSInputFile(final_mp3),
                reply_markup=music_actions_keyboard(query_key)
            )
            add_cache(f"orig_{query_key}", sent_audio.audio.file_id)
            os.remove(final_mp3)
            await msg.delete()
        except Exception as e:
            await msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")

@dp.callback_query(F.data.startswith(("ly_", "8d_", "sl_")))
async def handle_music_actions(callback: types.CallbackQuery):
    action, query_key = callback.data.split("_", 1)
    user_id = callback.from_user.id
    
    if action == "ly":
        lyrics = get_lyrics(query_key)
        await callback.message.reply(f"📝 **Matn:**\n\n{lyrics[:4000]}", parse_mode="Markdown")
        return await callback.answer()

    cache_key = f"{action}_{query_key}"
    cached_effect_id = get_cache(cache_key)
    
    if cached_effect_id:
        await bot.send_audio(chat_id=user_id, audio=cached_effect_id)
        return await callback.answer()

    orig_file_id = get_cache(f"orig_{query_key}")
    if not orig_file_id:
        return await callback.answer("❌ Original fayl bazadan topilmadi. Qaytadan izlang.", show_alert=True)

    await callback.answer("⏳ Jarayon boshlandi, biroz kuting...")
    
    file = await bot.get_file(orig_file_id)
    temp_orig = f"downloads/temp_{query_key}.mp3"
    temp_effect = f"downloads/{action}_{query_key}.mp3"
    
    await bot.download_file(file.file_path, destination=temp_orig)
    
    if action == "8d":
        make_8d(temp_orig, temp_effect)
    elif action == "sl":
        make_slowed(temp_orig, temp_effect)
        
    sent_effect = await bot.send_audio(chat_id=user_id, audio=FSInputFile(temp_effect))
    add_cache(cache_key, sent_effect.audio.file_id)
    
    os.remove(temp_orig)
    os.remove(temp_effect)

async def main():
    init_db()
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
