from pydub import AudioSegment
import math

def make_slowed(input_path, output_path):
    sound = AudioSegment.from_file(input_path)
    slowed_sound = sound._spawn(sound.raw_data, overrides={
        "frame_rate": int(sound.frame_rate * 0.85)
    }).set_frame_rate(sound.frame_rate)
    slowed_sound.export(output_path, format="mp3", bitrate="192k")
    return output_path

def make_8d(input_path, output_path):
    sound = AudioSegment.from_file(input_path)
    pan_limit = 0.9  
    chunk_length = 100 
    chunks = len(sound) // chunk_length
    eight_d_sound = AudioSegment.empty()
    for i in range(chunks):
        pan = math.sin(i / 10.0) * pan_limit
        chunk = sound[i * chunk_length : (i + 1) * chunk_length]
        chunk = chunk.pan(pan)
        eight_d_sound += chunk
    eight_d_sound.export(output_path, format="mp3", bitrate="192k")
    return output_path

def make_concert_hall(input_path, output_path):
    # Konsert zali effekti (Echo/Reverb)
    sound = AudioSegment.from_file(input_path)
    delay = sound - 7 
    empty = AudioSegment.silent(duration=150) 
    delayed_sound = empty + delay
    concert = sound.overlay(delayed_sound)
    concert.export(output_path, format="mp3", bitrate="192k")
    return output_path

