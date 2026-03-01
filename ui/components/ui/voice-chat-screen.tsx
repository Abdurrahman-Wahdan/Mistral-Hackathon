"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { VoicePoweredOrb } from "@/components/ui/voice-powered-orb";
import { Button } from "@/components/ui/button";

interface VoiceChatScreenProps {
  jobTitle: string;
  initialSessionId?: string | null;
  onClose: () => void;
  onComplete: (sessionId: string | null) => void;
}

type RingState = "connecting" | "active" | "failed";

const START_MAX_ATTEMPTS = 4;
const RETRYABLE_STATUSES = new Set([429, 502, 503, 504]);
const SILENCE_STOP_MS = 2000;
const VOLUME_THRESHOLD_INT16 = 2800;
const VOICE_CONFIRM_COUNT = 3;
const NO_SPEECH_TIMEOUT_MS = 8000;
const MAX_RECORDING_MS = 20000;
const MAX_POST_SPEECH_MS = 12000;
const TTS_FETCH_TIMEOUT_MS = 45_000;

function computeTtsGuardMs(text: string): number {
  const byLength = text.length * 120;
  return Math.min(75_000, Math.max(15_000, byLength));
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalizeErrorMessage(fallback: string, details: unknown): string {
  if (typeof details === "string" && details.trim()) return details.trim();
  if (details && typeof details === "object") {
    try {
      return `${fallback} ${JSON.stringify(details)}`;
    } catch {
      return fallback;
    }
  }
  return fallback;
}

function pickRecorderMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  for (const type of candidates) {
    if (MediaRecorder.isTypeSupported(type)) return type;
  }
  return undefined;
}

export default function VoiceChatScreen({
  jobTitle,
  initialSessionId,
  onClose,
  onComplete,
}: VoiceChatScreenProps) {
  const [voiceDetected, setVoiceDetected] = useState(false);
  const [ringState, setRingState] = useState<RingState>("connecting");
  const [isListening, setIsListening] = useState(false);
  const [statusText, setStatusText] = useState("Initializing interview...");
  const [error, setError] = useState<string | null>(null);
  const [endInterview, setEndInterview] = useState(false);

  const sessionIdRef = useRef<string | null>(null);
  const closedRef = useRef(false);
  const hasStartedRef = useRef(false);
  const finishingRef = useRef(false);
  const sendingTurnRef = useRef(false);
  const assistantSpeakingRef = useRef(false);
  const endInterviewRef = useRef(false);

  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const currentAudioUrlRef = useRef<string | null>(null);
  const speakRequestSeqRef = useRef(0);

  const micStreamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const monitorRafRef = useRef<number | null>(null);
  const hardStopTimerRef = useRef<number | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const shouldProcessRecordingRef = useRef(false);
  const speechStartedRef = useRef(false);
  const speechStartedAtRef = useRef(0);
  const loudStreakRef = useRef(0);
  const lastSpeechAtRef = useRef(0);
  const listenStartedAtRef = useRef(0);

  const speakAssistantRef = useRef<(text: string) => void>(() => {});
  const finishInterviewRef = useRef<() => void>(() => {});

  const clearMonitorRaf = useCallback(() => {
    if (monitorRafRef.current !== null) {
      window.cancelAnimationFrame(monitorRafRef.current);
      monitorRafRef.current = null;
    }
  }, []);

  const clearHardStopTimer = useCallback(() => {
    if (hardStopTimerRef.current !== null) {
      window.clearTimeout(hardStopTimerRef.current);
      hardStopTimerRef.current = null;
    }
  }, []);

  const cleanupMicResources = useCallback(() => {
    clearMonitorRaf();
    clearHardStopTimer();

    try {
      sourceNodeRef.current?.disconnect();
    } catch {
      // no-op
    }
    sourceNodeRef.current = null;
    analyserRef.current = null;

    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }

    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((track) => track.stop());
      micStreamRef.current = null;
    }

    mediaRecorderRef.current = null;
    setIsListening(false);
  }, [clearHardStopTimer, clearMonitorRaf]);

  const closePlayback = useCallback(() => {
    speakRequestSeqRef.current += 1;
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
    }
    if (currentAudioUrlRef.current) {
      URL.revokeObjectURL(currentAudioUrlRef.current);
      currentAudioUrlRef.current = null;
    }
  }, []);

  const stopListeningCapture = useCallback(
    (processRecording: boolean) => {
      setIsListening(false);
      shouldProcessRecordingRef.current = processRecording;
      clearMonitorRaf();
      clearHardStopTimer();

      const recorder = mediaRecorderRef.current;
      if (recorder && recorder.state !== "inactive") {
        try {
          recorder.stop();
        } catch {
          cleanupMicResources();
        }
      } else {
        cleanupMicResources();
      }
    },
    [cleanupMicResources, clearHardStopTimer, clearMonitorRaf]
  );

  const closeAll = useCallback(() => {
    stopListeningCapture(false);
    closePlayback();
  }, [closePlayback, stopListeningCapture]);

  const sendTurn = useCallback(async (candidateText: string) => {
    const sid = sessionIdRef.current;
    const content = (candidateText || "").trim();
    if (!content) return;
    if (!sid) {
      setError("Session is not ready yet. Please wait a moment and try again.");
      return;
    }

    sendingTurnRef.current = true;
    setStatusText("Processing your answer...");
    setError(null);

    try {
      const response = await fetch("/api/interview-session/turn", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: sid, candidateMessage: content }),
      });

      const body = (await response.json().catch(() => null)) as {
        assistant_message?: string;
        end_interview?: boolean;
        details?: unknown;
      } | null;

      if (!response.ok) {
        throw new Error(normalizeErrorMessage("Turn failed.", body?.details));
      }

      const shouldEnd = Boolean(body?.end_interview);
      endInterviewRef.current = shouldEnd;
      setEndInterview(shouldEnd);
      speakAssistantRef.current((body?.assistant_message ?? "").trim());
    } catch (err) {
      console.error("[VoiceInterview] Turn failed:", err);
      setError(err instanceof Error ? err.message : "Turn failed.");
      sendingTurnRef.current = false;
    }
  }, []);

  const processRecordedAudio = useCallback(
    async (audioBlob: Blob) => {
      if (closedRef.current || endInterviewRef.current || assistantSpeakingRef.current) {
        return;
      }

      if (!audioBlob.size) {
        setStatusText("Listening...");
        setError(null);
        return;
      }

      setStatusText("Transcribing...");
      setError(null);

      try {
        const formData = new FormData();
        formData.append("audio", audioBlob, "speech.webm");

        const sttRes = await fetch("/api/stt", {
          method: "POST",
          body: formData,
        });

        const sttBody = (await sttRes.json().catch(() => null)) as
          | { transcript?: string; detail?: unknown; error?: string }
          | null;

        if (!sttRes.ok) {
          throw new Error(
            normalizeErrorMessage(
              "STT failed.",
              sttBody?.detail ?? sttBody?.error ?? sttBody
            )
          );
        }

        const transcript = (sttBody?.transcript ?? "").trim();
        if (!transcript) {
          setStatusText("Did not catch that. Listening again...");
          return;
        }

        await sendTurn(transcript);
      } catch (err) {
        console.error("[VoiceInterview] STT failed:", err);
        setError(err instanceof Error ? err.message : "STT failed.");
      }
    },
    [sendTurn]
  );

  const startListeningCapture = useCallback(async () => {
    if (closedRef.current || endInterviewRef.current || assistantSpeakingRef.current || sendingTurnRef.current) {
      return;
    }

    stopListeningCapture(false);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      });

      micStreamRef.current = stream;

      const mimeType = pickRecorderMimeType();
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      mediaRecorderRef.current = recorder;
      recordedChunksRef.current = [];
      speechStartedRef.current = false;
      speechStartedAtRef.current = 0;
      loudStreakRef.current = 0;
      lastSpeechAtRef.current = 0;
      listenStartedAtRef.current = performance.now();
      shouldProcessRecordingRef.current = false;

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) {
          recordedChunksRef.current.push(event.data);
        }
      };

      recorder.onerror = () => {
        setError("Microphone recording failed.");
        cleanupMicResources();
      };

      recorder.onstop = () => {
        const shouldProcess = shouldProcessRecordingRef.current;
        const blobType = recorder.mimeType || "audio/webm";
        const blob = new Blob(recordedChunksRef.current, { type: blobType });
        cleanupMicResources();

        if (!shouldProcess || closedRef.current) {
          if (!closedRef.current && !assistantSpeakingRef.current && !endInterviewRef.current) {
            void startListeningCapture();
          }
          return;
        }

        void processRecordedAudio(blob).finally(() => {
          sendingTurnRef.current = false;
          if (!closedRef.current && !assistantSpeakingRef.current && !endInterviewRef.current) {
            void startListeningCapture();
          }
        });
      };

      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;
      if (audioContext.state === "suspended") {
        await audioContext.resume().catch(() => {});
      }
      const source = audioContext.createMediaStreamSource(stream);
      sourceNodeRef.current = source;
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 2048;
      analyser.smoothingTimeConstant = 0.2;
      analyserRef.current = analyser;
      source.connect(analyser);

      const waveform = new Uint8Array(analyser.fftSize);
      const monitor = () => {
        const activeAnalyser = analyserRef.current;
        const activeRecorder = mediaRecorderRef.current;
        if (!activeAnalyser || !activeRecorder || activeRecorder.state === "inactive") {
          return;
        }

        activeAnalyser.getByteTimeDomainData(waveform);
        const now = performance.now();
        let peak = 0;
        for (let i = 0; i < waveform.length; i += 1) {
          const dist = Math.abs(waveform[i] - 128);
          if (dist > peak) peak = dist;
        }
        const peakInt16 = Math.round((peak / 128) * 32767);

        if (peakInt16 >= VOLUME_THRESHOLD_INT16) {
          loudStreakRef.current += 1;
          if (loudStreakRef.current >= VOICE_CONFIRM_COUNT) {
            if (!speechStartedRef.current) {
              speechStartedRef.current = true;
              speechStartedAtRef.current = now;
            }
            lastSpeechAtRef.current = now;
          }
        } else {
          loudStreakRef.current = 0;
        }

        if (speechStartedRef.current && now - lastSpeechAtRef.current >= SILENCE_STOP_MS) {
          stopListeningCapture(true);
          return;
        }

        if (speechStartedRef.current && now - speechStartedAtRef.current >= MAX_POST_SPEECH_MS) {
          stopListeningCapture(true);
          return;
        }

        if (!speechStartedRef.current && now - listenStartedAtRef.current >= NO_SPEECH_TIMEOUT_MS) {
          setStatusText("No speech detected. Listening again...");
          stopListeningCapture(false);
          return;
        }

        if (now - listenStartedAtRef.current >= MAX_RECORDING_MS) {
          stopListeningCapture(speechStartedRef.current);
          return;
        }

        monitorRafRef.current = window.requestAnimationFrame(monitor);
      };

      recorder.start(200);
      hardStopTimerRef.current = window.setTimeout(() => {
        stopListeningCapture(speechStartedRef.current);
      }, MAX_RECORDING_MS + 1000);
      setRingState("active");
      setStatusText("Listening...");
      setError(null);
      setIsListening(true);
      monitorRafRef.current = window.requestAnimationFrame(monitor);
    } catch (err) {
      console.error("[VoiceInterview] Mic start failed:", err);
      setRingState("failed");
      setError("Could not access microphone.");
      setStatusText("Microphone unavailable.");
      cleanupMicResources();
    }
  }, [cleanupMicResources, processRecordedAudio, stopListeningCapture]);

  const speakAssistant = useCallback(
    async (text: string) => {
      assistantSpeakingRef.current = true;
      stopListeningCapture(false);
      setStatusText("Interviewer is speaking...");

      const normalized = (text || "").trim();
      const speakSeq = speakRequestSeqRef.current;
      const ttsGuardMs = computeTtsGuardMs(normalized);
      let settled = false;
      let guardTimer: number | null = null;

      const handoffToUser = () => {
        if (settled) return;
        settled = true;
        if (guardTimer !== null) {
          window.clearTimeout(guardTimer);
          guardTimer = null;
        }
        assistantSpeakingRef.current = false;
        sendingTurnRef.current = false;
        if (endInterviewRef.current) {
          finishInterviewRef.current();
          return;
        }
        void startListeningCapture();
      };

      guardTimer = window.setTimeout(() => {
        // Hard fallback so the UI never gets stuck at "Interviewer is speaking...".
        closePlayback();
        handoffToUser();
      }, ttsGuardMs);

      if (!normalized) {
        handoffToUser();
        return;
      }

      try {
        const controller = new AbortController();
        const ttsTimeout = window.setTimeout(() => controller.abort(), TTS_FETCH_TIMEOUT_MS);
        const response = await fetch("/api/tts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: normalized }),
          signal: controller.signal,
        });
        window.clearTimeout(ttsTimeout);

        if (speakSeq !== speakRequestSeqRef.current) return;
        if (!response.ok) {
          throw new Error(`TTS failed (${response.status})`);
        }

        const blob = await response.blob();
        if (speakSeq !== speakRequestSeqRef.current) return;

        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        currentAudioRef.current = audio;
        currentAudioUrlRef.current = url;

        audio.onended = () => {
          if (speakSeq !== speakRequestSeqRef.current) return;
          closePlayback();
          handoffToUser();
        };

        audio.onerror = () => {
          if (speakSeq !== speakRequestSeqRef.current) return;
          closePlayback();
          handoffToUser();
        };

        const playPromise = audio.play();
        if (playPromise) {
          await playPromise;
        }
      } catch (err) {
        if (speakSeq !== speakRequestSeqRef.current) return;
        console.error("[VoiceInterview] TTS failed:", err);
        setError(err instanceof Error ? err.message : "TTS failed.");
        closePlayback();
        handoffToUser();
      }
    },
    [closePlayback, startListeningCapture, stopListeningCapture]
  );

  useEffect(() => {
    speakAssistantRef.current = (text: string) => {
      void speakAssistant(text);
    };
  }, [speakAssistant]);

  const finishInterview = useCallback(async () => {
    if (finishingRef.current) return;
    finishingRef.current = true;
    setStatusText("Generating your report...");

    const sid = sessionIdRef.current;
    closeAll();

    if (!sid) {
      onComplete(null);
      finishingRef.current = false;
      return;
    }

    try {
      await fetch("/api/interview-session/finish", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId: sid, jobTitle, force: true }),
      });
    } catch (err) {
      console.error("[VoiceInterview] Finalize failed:", err);
    } finally {
      onComplete(sid);
      finishingRef.current = false;
    }
  }, [closeAll, jobTitle, onComplete]);

  useEffect(() => {
    finishInterviewRef.current = () => {
      void finishInterview();
    };
  }, [finishInterview]);

  useEffect(() => {
    let cancelled = false;

    const startSession = async () => {
      if (hasStartedRef.current) return;
      hasStartedRef.current = true;
      setRingState("connecting");
      setStatusText("Connecting...");
      setError(null);

      const preparedSessionId = (initialSessionId ?? "").trim();
      if (!preparedSessionId) {
        setRingState("failed");
        setStatusText("Session preparation required.");
        setError("Interview session was not prepared. Please go back and retry CV analysis.");
        return;
      }

      let lastError: unknown = null;
      for (let attempt = 1; attempt <= START_MAX_ATTEMPTS && !cancelled; attempt += 1) {
        try {
          const response = await fetch("/api/interview-session/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ jobTitle, sessionId: preparedSessionId }),
          });

          const body = (await response.json().catch(() => null)) as {
            session_id?: string;
            assistant_message?: string;
            end_interview?: boolean;
            details?: unknown;
          } | null;

          if (!response.ok) {
            const retryable = RETRYABLE_STATUSES.has(response.status);
            lastError = new Error(normalizeErrorMessage("Could not start session.", body?.details ?? body));
            if (!retryable || attempt === START_MAX_ATTEMPTS) {
              throw lastError;
            }
            await wait(Math.min(250 * 2 ** (attempt - 1), 1800));
            continue;
          }

          if (cancelled) return;

          const sid = (body?.session_id ?? "").trim() || preparedSessionId;
          sessionIdRef.current = sid || null;
          const shouldEnd = Boolean(body?.end_interview);
          endInterviewRef.current = shouldEnd;
          setEndInterview(shouldEnd);
          setRingState("active");
          setStatusText("Connected.");
          speakAssistantRef.current((body?.assistant_message ?? "").trim());
          return;
        } catch (err) {
          lastError = err;
          if (attempt === START_MAX_ATTEMPTS) break;
          await wait(Math.min(250 * 2 ** (attempt - 1), 1800));
        }
      }

      if (!cancelled) {
        console.error("[VoiceInterview] Start session failed:", lastError);
        setRingState("failed");
        setError(lastError instanceof Error ? lastError.message : "Could not start session.");
        setStatusText("Session startup failed.");
      }
    };

    void startSession();

    return () => {
      cancelled = true;
      closedRef.current = true;
      hasStartedRef.current = false;
      closeAll();
    };
  }, [closeAll, initialSessionId, jobTitle]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      closeAll();
      onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [closeAll, onClose]);

  return (
    <section className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black px-5 py-6">
      <motion.p
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="absolute top-8 text-foreground/30 text-sm font-medium tracking-wide"
      >
        Live AI Interview - {jobTitle}
      </motion.p>

      <motion.div
        initial={{ opacity: 0, scale: 0.85 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.6 }}
        className="relative h-56 w-56 sm:h-72 sm:w-72"
      >
        <VoicePoweredOrb
          enableVoiceControl={true}
          className="overflow-hidden rounded-full"
          onVoiceDetected={setVoiceDetected}
        />
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.25 }}
        className="mt-6 flex flex-col items-center gap-2"
      >
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${(isListening || voiceDetected) ? "bg-green-400" : "bg-foreground/35"}`}
          />
          <p className="text-sm text-foreground/60">{statusText}</p>
        </div>
        <p className="text-xs text-foreground/45">
          {ringState === "connecting"
            ? "Connecting interview..."
            : ringState === "active"
              ? "Voice channel active"
              : "Voice channel unavailable"}
        </p>
        {error && <p className="text-sm text-red-300">{error}</p>}
      </motion.div>

      <div className="fixed bottom-6 left-6 z-50">
        <Button
          size="lg"
          variant="outline"
          className="border-white/20 text-foreground backdrop-blur-xl hover:bg-white/10"
          onClick={() => {
            closeAll();
            onClose();
          }}
        >
          Exit Session
        </Button>
      </div>

      <div className="fixed bottom-6 right-6 z-50">
        <Button
          size="lg"
          className="bg-white text-black hover:bg-white/90"
          onClick={() => void finishInterview()}
        >
          {endInterview ? "View Final Review" : "Finish Interview"}
        </Button>
      </div>
    </section>
  );
}
