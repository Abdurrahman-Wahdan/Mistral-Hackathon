import asyncio
import json
import re
import time as time_mod
from difflib import SequenceMatcher
from typing import Any, Generator

from fastapi import FastAPI, Form, HTTPException, Response, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from hackathon.config.settings import settings
from hackathon.core.agents.interview_runtime import (
    InterviewSessionManager,
    _materialize_session_job_description,
    DATA_DIR,
    project_root,
)
from hackathon.core.agents.generate_questions import generate_questions_to_dir


class StartSessionRequest(BaseModel):
    session_id: str | None = None
    job_title: str | None = None


class StartSessionResponse(BaseModel):
    session_id: str
    created_at: str
    assistant_message: str
    end_interview: bool = False


class TurnRequest(BaseModel):
    candidate_message: str = Field(min_length=1, max_length=5000)


class TurnResponse(BaseModel):
    session_id: str
    assistant_message: str
    end_interview: bool
    turn_count: int
    progress: dict[str, Any]


class FinishRequest(BaseModel):
    force: bool = True
    job_title: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    created_at: str
    updated_at: str
    turn_count: int
    ended: bool
    outputs_dir: str


app = FastAPI(title="Interview Agent API", version="1.0.0")
manager = InterviewSessionManager()


def _parse_cors_origins() -> list[str]:
    raw = settings.INTERVIEW_API_CORS_ORIGINS.strip()
    if not raw:
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Echo filtering (same logic as elevenlabs_test.py) ────────────────────────

def _normalize_for_match(text: str) -> str:
    lowered = (text or "").lower()
    normalized = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", normalized).strip()


def _looks_like_echo(candidate: str, assistant: str, threshold: float = 0.68) -> bool:
    cand = _normalize_for_match(candidate)
    asst = _normalize_for_match(assistant)
    if not cand or not asst:
        return False
    if len(cand) >= 4 and cand in asst:
        return True
    if len(asst) >= 4 and asst in cand:
        return True
    seq = SequenceMatcher(None, cand, asst).ratio()
    cand_toks = set(cand.split())
    if not cand_toks:
        return seq >= threshold
    overlap = len(cand_toks & set(asst.split())) / len(cand_toks)
    return max(seq, overlap) >= threshold


# ─────────────────────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/interview/sessions", response_model=StartSessionResponse)
async def start_session(payload: StartSessionRequest) -> StartSessionResponse:
    try:
        state, assistant_message = await manager.create_session(
            session_id=payload.session_id,
            job_title=payload.job_title,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed to start session: {exc}") from exc

    return StartSessionResponse(
        session_id=state.session_id,
        created_at=state.created_at,
        assistant_message=assistant_message,
        end_interview=state.ended,
    )


@app.get("/v1/interview/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionResponse:
    state = await manager.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session_not_found")
    return SessionResponse(
        session_id=state.session_id,
        created_at=state.created_at,
        updated_at=state.updated_at,
        turn_count=state.turn_count,
        ended=state.ended,
        outputs_dir=str(state.outputs_dir),
    )


@app.post("/v1/interview/sessions/{session_id}/turn", response_model=TurnResponse)
async def turn(session_id: str, payload: TurnRequest) -> TurnResponse:
    try:
        result = await manager.process_turn(
            session_id=session_id,
            candidate_message=payload.candidate_message,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="session_not_found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"turn_failed: {exc}") from exc

    return TurnResponse(**result)


@app.post("/v1/interview/sessions/{session_id}/finish")
async def finish(session_id: str, payload: FinishRequest) -> dict[str, Any]:
    try:
        summary = await manager.finish_session(session_id=session_id, force=payload.force)
        review_payload = await manager.build_review_payload(
            session_id=session_id,
            job_title=payload.job_title or "",
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="session_not_found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"finish_failed: {exc}") from exc

    return {
        "session_id": session_id,
        "summary": summary,
        "review": review_payload,
    }


@app.get("/v1/interview/sessions/{session_id}/report")
async def report(session_id: str, job_title: str = "") -> dict[str, Any]:
    try:
        payload = await manager.build_review_payload(session_id=session_id, job_title=job_title)
    except KeyError:
        raise HTTPException(status_code=404, detail="session_not_found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"report_failed: {exc}") from exc
    return payload


@app.post("/v1/stt")
async def stt_endpoint(audio: UploadFile = File(...)) -> dict[str, str]:
    import io
    from elevenlabs import ElevenLabs

    if not settings.ELEVENLABS_API_KEY:
        raise HTTPException(status_code=503, detail="ELEVENLABS_API_KEY not configured")

    client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
    audio_bytes = await audio.read()
    filename = audio.filename or "audio.webm"
    content_type = audio.content_type or "audio/webm"

    def _transcribe() -> str:
        buf = io.BytesIO(audio_bytes)
        result = client.speech_to_text.convert(
            file=(filename, buf, content_type),
            model_id="scribe_v1",
        )
        return getattr(result, "text", "").strip()

    try:
        transcript = await asyncio.to_thread(_transcribe)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"stt_failed: {exc}") from exc

    return {"transcript": transcript}


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


@app.post("/v1/tts")
async def tts(payload: TTSRequest) -> StreamingResponse:
    from elevenlabs import ElevenLabs
    import queue
    import threading

    if not settings.ELEVENLABS_API_KEY:
        raise HTTPException(status_code=503, detail="ELEVENLABS_API_KEY not configured")

    client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
    chunk_queue: queue.Queue[bytes | None] = queue.Queue()

    def _stream_to_queue() -> None:
        try:
            for chunk in client.text_to_speech.stream(
                voice_id=settings.ELEVENLABS_VOICE_ID,
                text=payload.text,
                model_id="eleven_multilingual_v2",
                output_format="mp3_44100_128",
            ):
                if chunk:
                    chunk_queue.put(chunk)
        except Exception as exc:
            chunk_queue.put(None)
            raise exc
        finally:
            chunk_queue.put(None)

    threading.Thread(target=_stream_to_queue, daemon=True).start()

    def _iter_chunks() -> Generator[bytes, None, None]:
        while True:
            chunk = chunk_queue.get()
            if chunk is None:
                break
            yield chunk

    return StreamingResponse(
        _iter_chunks(),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/v1/prepare-session")
async def prepare_session(
    file: UploadFile = File(...),
    job_title: str = Form(""),
) -> dict[str, Any]:
    """
    Upload a CV PDF, generate tailored interview questions, and return a
    session_id that is ready to use with /v1/interview/sessions.

    This endpoint is the 'analyzing' step: it runs the full question-generation
    pipeline (~30–60 s) scoped to the uploaded candidate profile.
    """
    from uuid import uuid4

    session_id = f"session_{uuid4().hex[:12]}"
    session_dir = project_root / "outputs" / "sessions" / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # ── Extract text from uploaded file ─────────────────────────────────────
    file_bytes = await file.read()
    cv_text = ""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = [page.get_text() for page in doc]
        doc.close()
        cv_text = "\n\n".join(p for p in pages if p.strip())
    except Exception:
        # Fallback: try plain-text (e.g. .txt upload or missing pymupdf)
        try:
            cv_text = file_bytes.decode("utf-8", errors="replace")
        except Exception:
            pass

    if not cv_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from uploaded file.")

    # ── Persist CV and job description to session dir ────────────────────────
    (session_dir / "candidate.md").write_text(cv_text, encoding="utf-8")
    _materialize_session_job_description(session_dir, job_title or None)

    # ── Read JD + culture for question generation ────────────────────────────
    jd_path = session_dir / "job_description.md"
    jd_content = jd_path.read_text(encoding="utf-8") if jd_path.exists() else ""

    culture_path = DATA_DIR / "company_culture.md"
    culture_content = culture_path.read_text(encoding="utf-8") if culture_path.exists() else ""

    # ── Run question generation agents ───────────────────────────────────────
    try:
        await generate_questions_to_dir(cv_text, jd_content, culture_content, session_dir)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"question_generation_failed: {exc}") from exc

    question_bank_path = session_dir / "question_bank.json"
    if not question_bank_path.exists():
        raise HTTPException(status_code=500, detail="question_generation_failed: missing_question_bank")

    try:
        question_bank = json.loads(question_bank_path.read_text(encoding="utf-8"))
        categories = question_bank.get("categories", {})
        if not isinstance(categories, dict) or not categories:
            raise ValueError("empty_categories")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"question_generation_failed: invalid_question_bank ({exc})") from exc

    return {
        "session_id": session_id,
        "question_categories_count": len(categories),
    }


@app.websocket("/v1/stt/realtime")
async def stt_realtime_ws(websocket: WebSocket) -> None:
    """
    Realtime STT proxy: streams PCM audio from browser → ElevenLabs scribe_v2_realtime,
    applies echo filtering, and sends back transcript/barge_in events.

    Browser binary frames  → raw Int16 PCM at 16 kHz mono
    Browser text frames    → JSON control: {"type":"agent_speaking","text":"..."} | {"type":"agent_done"}
    Server sends back      → {"type":"transcript","text":"..."} | {"type":"barge_in","text":"..."} | {"type":"error","message":"..."}
    """
    import base64
    import json as _json
    from elevenlabs import AudioFormat, CommitStrategy, ElevenLabs, RealtimeEvents

    await websocket.accept()

    if not settings.ELEVENLABS_API_KEY:
        await websocket.send_json({"type": "error", "message": "ELEVENLABS_API_KEY not configured"})
        await websocket.close()
        return

    client = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
    outbound: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=64)

    state: dict[str, Any] = {
        "agent_speaking": False,
        "last_agent_msg": "",
        "last_tts_end": 0.0,
    }

    def on_partial(data: dict) -> None:
        text = str((data or {}).get("text", "")).strip()
        if not text:
            return
        if _looks_like_echo(text, state["last_agent_msg"]):
            return
        # Barge-in: user spoke meaningfully while agent was speaking
        if state["agent_speaking"] and len(text) >= 6:
            try:
                outbound.put_nowait({"type": "barge_in", "text": text})
            except asyncio.QueueFull:
                pass

    def on_committed(data: dict) -> None:
        text = str((data or {}).get("text", "")).strip()
        if not text or len(text) < 2:
            return
        if _looks_like_echo(text, state["last_agent_msg"]):
            return
        # Echo guard: ignore echo-like text briefly after TTS ends
        if (
            not state["agent_speaking"]
            and state["last_tts_end"] > 0
            and (time_mod.monotonic() - state["last_tts_end"]) <= 1.0
            and _looks_like_echo(text, state["last_agent_msg"], threshold=0.60)
        ):
            return
        try:
            outbound.put_nowait({"type": "transcript", "text": text})
        except asyncio.QueueFull:
            pass

    try:
        connection = await client.speech_to_text.realtime.connect({
            "model_id": "scribe_v2_realtime",
            "audio_format": AudioFormat.PCM_16000,
            "sample_rate": 16000,
            "commit_strategy": CommitStrategy.VAD,
            "vad_silence_threshold_secs": 0.45,
            "include_timestamps": False,
        })
    except Exception as exc:
        await websocket.send_json({"type": "error", "message": f"Realtime STT unavailable: {exc}"})
        await websocket.close()
        return

    connection.on(RealtimeEvents.PARTIAL_TRANSCRIPT, on_partial)
    connection.on(RealtimeEvents.COMMITTED_TRANSCRIPT, on_committed)

    async def receive_loop() -> None:
        try:
            while True:
                data = await websocket.receive()
                if data.get("type") == "websocket.disconnect":
                    break
                if "bytes" in data:
                    encoded = base64.b64encode(data["bytes"]).decode("ascii")
                    await connection.send({"audio_base_64": encoded})
                elif "text" in data:
                    try:
                        msg = _json.loads(data["text"])
                        if msg.get("type") == "agent_speaking":
                            state["agent_speaking"] = True
                            state["last_agent_msg"] = msg.get("text", "")
                        elif msg.get("type") == "agent_done":
                            state["agent_speaking"] = False
                            state["last_tts_end"] = time_mod.monotonic()
                    except Exception:
                        pass
        except (WebSocketDisconnect, Exception):
            pass
        finally:
            try:
                outbound.put_nowait(None)
            except asyncio.QueueFull:
                pass

    async def send_loop() -> None:
        while True:
            msg = await outbound.get()
            if msg is None:
                break
            try:
                await websocket.send_json(msg)
            except Exception:
                break

    try:
        await asyncio.gather(receive_loop(), send_loop())
    finally:
        try:
            await connection.close()
        except Exception:
            pass


def main() -> None:
    import uvicorn

    uvicorn.run(
        app,
        host=settings.INTERVIEW_API_HOST,
        port=settings.INTERVIEW_API_PORT,
    )


if __name__ == "__main__":
    main()
