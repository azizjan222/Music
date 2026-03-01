import yt_dlp
from ytmusicapi import YTMusic
from shazamio import Shazam

ytmusic = YTMusic()

async def recognize_song(file_path):
    shazam = Shazam()
    out = await shazam.recognize_song(file_path)
    if out and 'track' in out:
        return f"{out['track']['subtitle']} - {out['track']['title']}"
    return None

def download_music(query, output_path_without_ext):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': output_path_without_ext,
        'noplaylist': True,
        'quiet': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # YouTube o'rniga SoundCloud'dan izlaymiz (blokirovkani aylanib o'tish uchun)
        ydl.download([f"scsearch1:{query}"])
        
    return f"{output_path_without_ext}.mp3"

def get_lyrics(query):
    search_results = ytmusic.search(query, filter="songs")
    if search_results:
        video_id = search_results[0]['videoId']
        try:
            watch_playlist = ytmusic.get_watch_playlist(videoId=video_id)
            lyrics_id = watch_playlist.get('lyrics')
            if lyrics_id:
                lyrics_dict = ytmusic.get_lyrics(lyrics_id)
                return lyrics_dict['lyrics']
        except Exception:
            return "Kechirasiz, bu qo'shiq matni topilmadi."
    return "Kechirasiz, bu qo'shiq matni topilmadi."
