import os
import io
import wave
import pyaudio
import numpy as np
from dotenv import load_dotenv
from elevenlabs import ElevenLabs

load_dotenv()

API_KEY = os.getenv("ELEVENLABS_API_KEY")
client = ElevenLabs(api_key=API_KEY)

# Config
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024
THRESHOLD = 2500  # Balanced: sensitive enough for normal speech, echo filtered by CONFIRM_COUNT
SILENCE_TIMEOUT = 2.0  # seconds of silence before stopping recording
CONFIRM_COUNT = 3  # consecutive loud chunks needed to confirm real speech
PRE_BUFFER_SIZE = 20  # number of mic chunks to keep as pre-buffer (~1.3 seconds)

# HR Agent text
AUDIO_TEXT = "Merhaba, ben Furkan. Yazılım mühendisliği alanında 3 yıllık deneyime sahibim. Özellikle web geliştirme ve bulut bilişim konularında kendimi geliştirdim. Yeni teknolojileri öğrenmeye ve problem çözmeye odaklı çalışıyorum."


def play_tts_with_interruption():
    """Play TTS audio. Returns (interrupted, pre_buffer).
    pre_buffer contains the mic data that triggered the interruption so first words aren't lost.
    """
    from collections import deque
    print("HR Agent speaking...")
    audio_stream = client.text_to_speech.stream(
        voice_id="21m00Tcm4TlvDq8ikWAM",
        output_format="pcm_16000",
        text=AUDIO_TEXT,
        model_id="eleven_multilingual_v2"
    )

    p = pyaudio.PyAudio()
    out_stream = p.open(format=pyaudio.paInt16, channels=CHANNELS, rate=SAMPLE_RATE, output=True)
    in_stream = p.open(format=pyaudio.paInt16, channels=CHANNELS, rate=SAMPLE_RATE,
                       input=True, frames_per_buffer=CHUNK_SIZE)

    interrupted = False
    loops = 0
    loud_streak = 0  # consecutive loud readings
    pre_buffer = deque(maxlen=PRE_BUFFER_SIZE)  # rolling buffer of mic data

    try:
        if in_stream.get_read_available() > 0:
            in_stream.read(in_stream.get_read_available(), exception_on_overflow=False)

        for chunk in audio_stream:
            if chunk:
                loops += 1
                available = in_stream.get_read_available()
                if available > 0:
                    data = in_stream.read(available, exception_on_overflow=False)
                    if loops > 10:  # longer warmup to let speaker settle
                        audio_data = np.frombuffer(data, dtype=np.int16)
                        volume = np.max(np.abs(audio_data)) if len(audio_data) > 0 else 0
                        if volume > THRESHOLD:
                            pre_buffer.append(data)  # only buffer user speech, not echo
                            loud_streak += 1
                            if loud_streak >= CONFIRM_COUNT:
                                print("\nUser speech detected! Stopping playback...")
                                interrupted = True
                                break
                        else:
                            loud_streak = 0
                out_stream.write(chunk)
    except KeyboardInterrupt:
        interrupted = True
    finally:
        out_stream.stop_stream()
        out_stream.close()
        in_stream.stop_stream()
        in_stream.close()
        p.terminate()

    return interrupted, list(pre_buffer)


def record_user_speech(pre_buffer=None):
    """Record user speech until silence is detected, return WAV bytes.
    pre_buffer: list of raw audio bytes from before recording started (to capture first words).
    """
    print("\nListening... (speak now, will stop after 2s of silence)")

    p = pyaudio.PyAudio()
    mic = p.open(format=pyaudio.paInt16, channels=CHANNELS, rate=SAMPLE_RATE,
                 input=True, frames_per_buffer=CHUNK_SIZE)

    # Start with pre-buffered audio (contains the speech that triggered interruption)
    frames = list(pre_buffer) if pre_buffer else []
    silent_chunks = 0
    max_silent = int(SILENCE_TIMEOUT * SAMPLE_RATE / CHUNK_SIZE)
    has_spoken = len(frames) > 0  # If we have pre-buffer, user already started speaking

    try:
        while True:
            data = mic.read(CHUNK_SIZE, exception_on_overflow=False)
            audio_data = np.frombuffer(data, dtype=np.int16)
            volume = np.max(np.abs(audio_data))

            if volume > THRESHOLD:
                has_spoken = True
                silent_chunks = 0
                frames.append(data)
            else:
                if has_spoken:
                    frames.append(data)
                    silent_chunks += 1
                    if silent_chunks >= max_silent:
                        print("Silence detected, stopping recording.")
                        break
    except KeyboardInterrupt:
        pass
    finally:
        mic.stop_stream()
        mic.close()
        p.terminate()

    # Convert to WAV in memory
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16-bit = 2 bytes
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(b''.join(frames))

    wav_buffer.seek(0)
    return wav_buffer


def transcribe_audio(wav_buffer):
    """Send WAV audio to ElevenLabs STT API and return text."""
    print("Transcribing...")
    result = client.speech_to_text.convert(
        file=wav_buffer,
        model_id="scribe_v1",
        language_code="tr",
    )
    return result.text


def main():
    # Step 1: HR Agent speaks
    interrupted, pre_buffer = play_tts_with_interruption()

    if interrupted:
        # Step 2: Record user speech (with pre-buffer so first words aren't lost)
        wav_buffer = record_user_speech(pre_buffer=pre_buffer)

        # Step 3: Transcribe
        transcript = transcribe_audio(wav_buffer)
        print(f"\n{'='*50}")
        print(f"User said: {transcript}")
        print(f"{'='*50}")
    else:
        print("HR Agent finished speaking (no interruption).")


if __name__ == "__main__":
    main()