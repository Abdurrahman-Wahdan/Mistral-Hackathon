import io
import os
import wave
import pyaudio
import numpy as np
import asyncio
from dotenv import load_dotenv
from elevenlabs import ElevenLabs
from hackathon.core.agents.interview_runtime import InterviewSessionManager

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

def play_tts_with_interruption(text: str):
    """Play TTS audio. Returns (interrupted, pre_buffer).
    pre_buffer contains the mic data that triggered the interruption so first words aren't lost.
    """
    from collections import deque
    print(f"\nHR Agent speaking: {text}")
    audio_stream = client.text_to_speech.stream(
        voice_id="21m00Tcm4TlvDq8ikWAM",
        output_format="pcm_16000",
        text=text,
        model_id="eleven_multilingual_v2"
    )

    p = pyaudio.PyAudio()
    out_stream = p.open(format=pyaudio.paInt16, channels=CHANNELS, rate=SAMPLE_RATE, output=True)
    in_stream = p.open(format=pyaudio.paInt16, channels=CHANNELS, rate=SAMPLE_RATE,
                       input=True, frames_per_buffer=CHUNK_SIZE)

    interrupted = False
    frames_played = 0
    loud_streak = 0  # consecutive loud readings
    pre_buffer = deque(maxlen=PRE_BUFFER_SIZE)  # rolling buffer of mic data

    try:
        if in_stream.get_read_available() > 0:
            in_stream.read(in_stream.get_read_available(), exception_on_overflow=False)

        for chunk in audio_stream:
            if not chunk: continue
            
            # Process the chunk in small pieces to keep the mic check frequent
            chunk_ptr = 0
            while chunk_ptr < len(chunk):
                # Write a small piece of the current chunk to the speaker
                write_size = min(len(chunk) - chunk_ptr, CHUNK_SIZE * 2)
                out_stream.write(chunk[chunk_ptr:chunk_ptr + write_size])
                chunk_ptr += write_size
                frames_played += write_size // 2
                
                # Immediately check the mic after every small write
                available = in_stream.get_read_available()
                if available > 0:
                    data = in_stream.read(available, exception_on_overflow=False)
                    # Use a very short warmup (0.2s) as the settle time is fast
                    if frames_played > int(SAMPLE_RATE * 0.2):
                        audio_data = np.frombuffer(data, dtype=np.int16)
                        
                        # Check volume in small windows for accuracy
                        for i in range(0, len(audio_data), CHUNK_SIZE):
                            sub_chunk = audio_data[i:i+CHUNK_SIZE]
                            if len(sub_chunk) == 0: continue
                            
                            volume = np.max(np.abs(sub_chunk))
                            if volume > THRESHOLD:
                                pre_buffer.append(sub_chunk.tobytes())
                                loud_streak += 1
                                if loud_streak >= CONFIRM_COUNT:
                                    print("\n[INTERRUPT] User speech detected! Breaking...")
                                    interrupted = True
                                    break
                            else:
                                if loud_streak > 0:
                                    loud_streak = 0
                
                if interrupted:
                    break
            
            if interrupted:
                break

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


async def main_async():
    if not API_KEY:
        print("ELEVENLABS_API_KEY eksik.")
        return

    manager = InterviewSessionManager()
    session_id = os.getenv("VOICE_SESSION_ID", "voice_session")
    job_title = os.getenv("VOICE_JOB_TITLE", "").strip() or None

    state, ai_text = await manager.create_session(session_id=session_id, job_title=job_title)
    print(f"\nSession started: {state.session_id}")
    print(f"Session logs: {state.outputs_dir}")

    try:
        while True:
            interrupted, pre_buffer = play_tts_with_interruption(ai_text)

            # Record user response (whether they interrupted or waited)
            wav_buffer = record_user_speech(pre_buffer=pre_buffer if interrupted else None)
            transcript = transcribe_audio(wav_buffer)

            print(f"\n{'='*50}")
            print(f"User said: {transcript}")
            print(f"{'='*50}")

            candidate_text = (transcript or "").strip()
            if not candidate_text:
                print("Sesiniz anlaşılamadı. Tekrar dinleniyor...")
                ai_text = "Dediğinizi tam anlayamadım, tekrar edebilir misiniz?"
                continue

            if candidate_text.lower() in {"quit", "exit", "stop"}:
                print("\nKullanıcı isteğiyle görüşme sonlandırıldı.")
                break

            print("\nInterview runtime düşünüyor...")
            result = await manager.process_turn(state.session_id, candidate_text)
            ai_text = str(result.get("assistant_message", "")).strip()
            if not ai_text:
                ai_text = "Teşekkür ederim. Biraz daha detay verebilir misiniz?"

            if bool(result.get("end_interview", False)):
                # Speak final assistant message before exiting.
                play_tts_with_interruption(ai_text)
                print("\nGörüşme doğal şekilde tamamlandı.")
                break
    except KeyboardInterrupt:
        print("\nGörüşme sonlandırıldı.")
    finally:
        try:
            summary = await manager.finish_session(state.session_id, force=True)
            reports_dir = summary.get("reports_dir")
            if reports_dir:
                print(f"Report directory: {reports_dir}")
        except Exception as exc:
            print(f"Rapor üretimi başarısız: {exc}")


if __name__ == "__main__":
    asyncio.run(main_async())
