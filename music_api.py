import yt_dlp
from ytmusicapi import YTMusic
from yandex_music import Client
from shazamio import Shazam
import os

ytmusic = YTMusic()
ym_client = Client().init()

async def recognize_song(file_path):
    shazam = Shazam()
    out = await shazam.recognize_song(file_path)
    if out and 'track' in out:
        return f"{out['track']['subtitle']} - {out['track']['title']}"
    return None

# LIMITNI 50 TA QILDIM (Ko'proq qo'shiq topadi)
def search_combined(query, limit=50):
    all_results = []
    try:
        ym_search = ym_client.search(query)
        if ym_search.tracks:
            for track in ym_search.tracks.results[:limit]:
                artists = ", ".join([a.name for a in track.artists])
                all_results.append({'title': f"{artists} - {track.title}", 'url': f"ymtrack_{track.id}"})
    except: pass
    try:
        yt_search = ytmusic.search(query, filter="songs")
        for item in yt_search[:limit]:
            all_results.append({'title': f"{item['artists'][0]['name']} - {item['title']}", 'url': f"https://music.youtube.com/watch?v={item['videoId']}"})
    except: pass
    return all_results

def download_music(url_or_id, output_path_without_ext):
    if url_or_id.startswith("ymtrack_"):
        track_id = url_or_id.split("_")[1]
        track = ym_client.tracks([track_id])[0]
        track.download(f"{output_path_without_ext}.mp3", bitrate_in_kbps=192)
    else:
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
            'outtmpl': output_path_without_ext,
            'quiet': True,
            'extractor_args': {'youtube': ['client=android']},
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url_or_id])
    return f"{output_path_without_ext}.mp3"

# YANGI: QO'SHIQ MATNINI TOPISH FUNKSIYASI
def get_lyrics_text(query):
    try:
        results = ytmusic.search(query, filter="songs")
        if results:
            vid = results[0]['videoId']
            watch = ytmusic.get_watch_playlist(videoId=vid)
            if 'lyrics' in watch and watch['lyrics']:
                lyrics = ytmusic.get_lyrics(watch['lyrics'])
                return lyrics['lyrics']
    except:
        pass
    return "❌ Uzr, bu qo'shiqning matni internet bazalaridan topilmadi."
