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

def search_track_list(query, limit=30):
    ydl_opts = {'extract_flat': True, 'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"scsearch{limit}:{query}", download=False)
            if info and 'entries' in info:
                results = []
                for entry in info['entries']:
                    results.append({'title': entry.get('title', 'Noma\'lum'), 'url': entry.get('url', '')})
                return results
        except Exception:
            return []
    return []

def download_music(url_or_query, output_path_without_ext):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'outtmpl': output_path_without_ext,
        'noplaylist': True,
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        if url_or_query.startswith('http'): ydl.download([url_or_query])
        else: ydl.download([f"scsearch1:{url_or_query}"])
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
        except: pass
    return "Kechirasiz, bu qo'shiq matni topilmadi."
