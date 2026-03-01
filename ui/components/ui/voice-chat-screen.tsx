"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { TalkingAvatar, type TalkingAvatarRef } from "@/components/ui/talking-avatar";
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

// ── Voice Activity Detection (VAD) tuning ──
// Silence after speech ends before we stop recording & send to STT.
// Keep short so the agent feels snappy, but long enough not to clip mid-pause.
const SILENCE_STOP_MS = 1400;
// Volume threshold — set so TTS echo through speakers doesn't trigger false
// positives (echo cancellation handles most of it).
const VOLUME_THRESHOLD_INT16 = 1100;
// Consecutive loud frames needed to confirm real speech.
const VOICE_CONFIRM_COUNT = 2;
// Wait for user to start speaking before sending whatever we have.
const NO_SPEECH_TIMEOUT_MS = 5000;
// Hard cap on any single recording window.
const MAX_RECORDING_MS = 30_000;
// After user starts speaking, max time before we force-stop.
const MAX_POST_SPEECH_MS = 25_000;

// ── TTS timeouts ──
const TTS_FETCH_TIMEOUT_MS = 45_000;
const TTS_BLOB_TIMEOUT_MS = 60_000;

function computeTtsNetworkGuardMs(text: string): number {
  const byLength = text.length * 90;
  return Math.min(60_000, Math.max(12_000, byLength));
}

function computeTtsPlaybackGuardMs(text: string, audioBytes: number): number {
  const byBytesMs = audioBytes > 0 ? Math.round((audioBytes / 16_000) * 1000) + 3_000 : 0;
  const words = text.split(/\s+/).filter(Boolean).length;
  const byWordsMs = words * 520 + 3_500;
  const estimate = Math.max(byBytesMs, byWordsMs);
  return Math.min(45_000, Math.max(10_000, estimate));
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number, message: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = window.setTimeout(() => reject(new Error(message)), timeoutMs);
    promise
      .then((value) => {
        window.clearTimeout(timer);
        resolve(value);
      })
      .catch((error) => {
        window.clearTimeout(timer);
        reject(error);
      });
  });
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
  const [ringState, setRingState] = useState<RingState>("connecting");
  const [isListening, setIsListening] = useState(false);
  const [statusText, setStatusText] = useState("Loading 3D avatar...");
  const [error, setError] = useState<string | null>(null);
  const [endInterview, setEndInterview] = useState(false);
  const [avatarReady, setAvatarReady] = useState(false);
  const [userVoiceLevel, setUserVoiceLevel] = useState(0);
  const [isAssistantSpeaking, setIsAssistantSpeaking] = useState(false);

  const sessionIdRef = useRef<string | null>(null);
  const closedRef = useRef(false);
  const hasStartedRef = useRef(false);
  const finishingRef = useRef(false);
  const sendingTurnRef = useRef(false);
  const assistantSpeakingRef = useRef(false);
  const endInterviewRef = useRef(false);
  // New: track whether we are in the process of starting listening to avoid
  // duplicate startListeningCapture calls racing each other.
  const startingListenRef = useRef(false);
  const avatarRef = useRef<TalkingAvatarRef>(null);

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
  const emptyTranscriptStreakRef = useRef(0);
  const isListeningRef = useRef(false);

  const speakAssistantRef = useRef<(text: string) => void>(() => { });
  const finishInterviewRef = useRef<() => void>(() => { });
  // New: a ref to call startListeningCapture from deeper callbacks safely.
  const startListeningCaptureRef = useRef<() => void>(() => { });

  const clearMonitorRaf = useCallback(() => {
    if (monitorRafRef.current !== null) {
      window.cancelAnimationFrame(monitorRafRef.current);
      monitorRafRef.current = null;
    }
  }, []);

  useEffect(() => {
    isListeningRef.current = isListening;
  }, [isListening]);

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
      audioContextRef.current.close().catch(() => { });
      audioContextRef.current = null;
    }

    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((track) => track.stop());
      micStreamRef.current = null;
    }

    mediaRecorderRef.current = null;
    setIsListening(false);
    setUserVoiceLevel(0);
    startingListenRef.current = false;
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
      setUserVoiceLevel(0);
      shouldProcessRecordingRef.current = processRecording;
      clearMonitorRaf();
      clearHardStopTimer();

      const recorder = mediaRecorderRef.current;
      if (recorder && recorder.state !== "inactive") {
        try {
          recorder.requestData();
        } catch {
          // no-op
        }
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

  // ── Helper: safely begin listening again ──
  // Checks all preconditions and avoids duplicate calls.
  const tryStartListening = useCallback(() => {
    if (closedRef.current) return;
    if (endInterviewRef.current) {
      // Interview ended — move to finish flow instead of listening.
      finishInterviewRef.current();
      return;
    }
    if (assistantSpeakingRef.current || sendingTurnRef.current) return;
    // Delegate to the ref so we get the latest version of startListeningCapture.
    startListeningCaptureRef.current();
  }, []);

  const sendTurn = useCallback(async (candidateText: string) => {
    const sid = sessionIdRef.current;
    const content = (candidateText || "").trim();
    if (!content) {
      // Nothing to send — go back to listening.
      sendingTurnRef.current = false;
      tryStartListening();
      return;
    }
    if (!sid) {
      setError("Session is not ready yet. Please wait a moment and try again.");
      sendingTurnRef.current = false;
      tryStartListening();
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

      // Important: clear sendingTurnRef BEFORE handing off to speakAssistant,
      // because speakAssistant's handoffToUser checks this flag.
      sendingTurnRef.current = false;

      speakAssistantRef.current((body?.assistant_message ?? "").trim());
    } catch (err) {
      console.error("[VoiceInterview] Turn failed:", err);
      setError(err instanceof Error ? err.message : "Turn failed.");
      sendingTurnRef.current = false;
      // On error, go back to listening so the user isn't stuck.
      tryStartListening();
    }
  }, [tryStartListening]);

  const processRecordedAudio = useCallback(
    async (audioBlob: Blob) => {
      if (closedRef.current || endInterviewRef.current || assistantSpeakingRef.current) {
        sendingTurnRef.current = false;
        return;
      }

      if (!audioBlob.size) {
        setStatusText("No audio captured. Listening again...");
        setError(null);
        sendingTurnRef.current = false;
        tryStartListening();
        return;
      }

      setStatusText("Transcribing...");
      setError(null);

      try {
        const formData = new FormData();
        const fileName = audioBlob.type.includes("mp4")
          ? "speech.m4a"
          : audioBlob.type.includes("ogg")
            ? "speech.ogg"
            : "speech.webm";
        formData.append("audio", audioBlob, fileName);

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
          emptyTranscriptStreakRef.current += 1;
          if (emptyTranscriptStreakRef.current >= 2) {
            setError("No speech detected from mic input. Check browser mic permission and selected input device.");
          }
          setStatusText("Did not catch that. Please speak louder and closer to the mic.");
          sendingTurnRef.current = false;
          tryStartListening();
          return;
        }
        emptyTranscriptStreakRef.current = 0;
        setError(null);

        // sendTurn will handle resetting sendingTurnRef and starting listening.
        await sendTurn(transcript);
      } catch (err) {
        console.error("[VoiceInterview] STT failed:", err);
        setError(err instanceof Error ? err.message : "STT failed.");
        sendingTurnRef.current = false;
        tryStartListening();
      }
    },
    [sendTurn, tryStartListening]
  );

  const startListeningCapture = useCallback(async () => {
    // Guard: don't start if any blocker is active.
    if (closedRef.current || assistantSpeakingRef.current || sendingTurnRef.current) {
      return;
    }
    if (endInterviewRef.current) {
      finishInterviewRef.current();
      return;
    }
    // Prevent duplicate starts.
    if (startingListenRef.current) return;
    startingListenRef.current = true;

    // Clean up any leftover recording (without processing).
    stopListeningCapture(false);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          // Enable echo cancellation so that TTS playback through speakers
          // doesn't get picked up as user speech.
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
          sampleRate: 16000,
        },
        video: false,
      });

      // Re-check guards after the async getUserMedia call.
      if (closedRef.current || assistantSpeakingRef.current || endInterviewRef.current) {
        stream.getTracks().forEach((t) => t.stop());
        startingListenRef.current = false;
        return;
      }

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
        // Try to recover by starting listening again after a brief delay.
        window.setTimeout(() => tryStartListening(), 500);
      };

      recorder.onstop = () => {
        const shouldProcess = shouldProcessRecordingRef.current;
        const blobType = recorder.mimeType || "audio/webm";
        const blob = new Blob(recordedChunksRef.current, { type: blobType });
        cleanupMicResources();

        if (!shouldProcess || closedRef.current) {
          // Not processing — just restart listening if appropriate.
          if (!closedRef.current && !assistantSpeakingRef.current && !endInterviewRef.current && !sendingTurnRef.current) {
            tryStartListening();
          }
          return;
        }

        // Mark that we are processing (sendingTurnRef) so overlapping
        // startListeningCapture calls won't fire.
        sendingTurnRef.current = true;

        void processRecordedAudio(blob);
      };

      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;
      if (audioContext.state === "suspended") {
        await audioContext.resume().catch(() => { });
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

        // If the assistant started speaking while we were monitoring, stop
        // immediately without processing.
        if (assistantSpeakingRef.current || closedRef.current) {
          setUserVoiceLevel(0);
          stopListeningCapture(false);
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

        // Normalized 0-1
        const normalizedLevel = Math.min(peakInt16 / 8000, 1);
        setUserVoiceLevel(normalizedLevel);

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

        // User stopped speaking — silence detected.
        if (speechStartedRef.current && now - lastSpeechAtRef.current >= SILENCE_STOP_MS) {
          stopListeningCapture(true);
          return;
        }

        // Hard cap: user has been speaking too long.
        if (speechStartedRef.current && now - speechStartedAtRef.current >= MAX_POST_SPEECH_MS) {
          stopListeningCapture(true);
          return;
        }

        // No speech at all for a long time — send whatever we have.
        if (!speechStartedRef.current && now - listenStartedAtRef.current >= NO_SPEECH_TIMEOUT_MS) {
          setStatusText("Low signal detected. Sending sample...");
          stopListeningCapture(true);
          return;
        }

        // Overall hard cap.
        if (now - listenStartedAtRef.current >= MAX_RECORDING_MS) {
          stopListeningCapture(true);
          return;
        }

        monitorRafRef.current = window.requestAnimationFrame(monitor);
      };

      recorder.start(200);
      hardStopTimerRef.current = window.setTimeout(() => {
        stopListeningCapture(true);
      }, MAX_RECORDING_MS + 1000);
      setRingState("active");
      setStatusText("Listening...");
      setError(null);
      setIsListening(true);
      startingListenRef.current = false;
      monitorRafRef.current = window.requestAnimationFrame(monitor);
    } catch (err) {
      console.error("[VoiceInterview] Mic start failed:", err);
      setRingState("failed");
      setError("Could not access microphone.");
      setStatusText("Microphone unavailable.");
      cleanupMicResources();
      startingListenRef.current = false;
    }
  }, [cleanupMicResources, processRecordedAudio, stopListeningCapture, tryStartListening]);

  // Keep the ref always pointing at the latest version.
  useEffect(() => {
    startListeningCaptureRef.current = () => {
      void startListeningCapture();
    };
  }, [startListeningCapture]);

  const speakAssistant = useCallback(
    async (text: string) => {
      assistantSpeakingRef.current = true;
      setIsAssistantSpeaking(true);
      // Stop any ongoing recording — we are about to play audio.
      stopListeningCapture(false);
      setStatusText("Interviewer is speaking...");
      // Give the avatar a visual feedback? No, TTS does it.


      const normalized = (text || "").trim();
      const speakSeq = speakRequestSeqRef.current;
      const networkGuardMs = computeTtsNetworkGuardMs(normalized);
      let settled = false;
      let guardTimer: number | null = null;
      let playbackWatchTimer: number | null = null;
      let listeningKickTimer1: number | null = null;
      let listeningKickTimer2: number | null = null;

      const handoffToUser = () => {
        if (settled) return;
        settled = true;
        if (guardTimer !== null) {
          window.clearTimeout(guardTimer);
          guardTimer = null;
        }
        if (playbackWatchTimer !== null) {
          window.clearTimeout(playbackWatchTimer);
          playbackWatchTimer = null;
        }
        if (listeningKickTimer1 !== null) {
          window.clearTimeout(listeningKickTimer1);
          listeningKickTimer1 = null;
        }
        if (listeningKickTimer2 !== null) {
          window.clearTimeout(listeningKickTimer2);
          listeningKickTimer2 = null;
        }
        assistantSpeakingRef.current = false;
        setIsAssistantSpeaking(false);
        sendingTurnRef.current = false;
        startingListenRef.current = false;

        avatarRef.current?.stopSpeaking();

        if (endInterviewRef.current) {
          finishInterviewRef.current();
          return;
        }
        if (closedRef.current) return;

        setStatusText("Listening...");
        // Use tryStartListening which has all the guards.
        tryStartListening();
        // Safety net: if listening did not start due race/permission edge, force retry.
        listeningKickTimer1 = window.setTimeout(() => {
          if (settled) return;
          if (closedRef.current || endInterviewRef.current || assistantSpeakingRef.current) return;
          if (!isListeningRef.current) {
            startListeningCaptureRef.current();
          }
        }, 900);
        listeningKickTimer2 = window.setTimeout(() => {
          if (settled) return;
          if (closedRef.current || endInterviewRef.current || assistantSpeakingRef.current) return;
          if (!isListeningRef.current) {
            setStatusText("Listening...");
            startListeningCaptureRef.current();
          }
        }, 2400);
      };

      const armGuard = (timeoutMs: number) => {
        if (guardTimer !== null) {
          window.clearTimeout(guardTimer);
          guardTimer = null;
        }
        guardTimer = window.setTimeout(() => {
          closePlayback();
          handoffToUser();
        }, timeoutMs);
      };

      const startPlaybackWatchdog = (audioEl: HTMLAudioElement) => {
        let lastTime = -1;
        let stagnantMs = 0;
        const tick = () => {
          if (settled || speakSeq !== speakRequestSeqRef.current) return;
          const duration = Number.isFinite(audioEl.duration) ? audioEl.duration : 0;
          const current = audioEl.currentTime;

          if (audioEl.ended) {
            closePlayback();
            handoffToUser();
            return;
          }
          if (duration > 0 && current >= duration - 0.1) {
            closePlayback();
            handoffToUser();
            return;
          }
          // Some browsers pause at the end without reliably firing `ended`.
          if (current > 0.15 && audioEl.paused && !audioEl.seeking) {
            closePlayback();
            handoffToUser();
            return;
          }
          // Detect playback stalls and recover.
          if (!audioEl.paused) {
            if (Math.abs(current - lastTime) < 0.001) {
              stagnantMs += 250;
            } else {
              stagnantMs = 0;
            }
          } else {
            stagnantMs = 0;
          }
          lastTime = current;
          if (current > 0.2 && stagnantMs >= 1500) {
            closePlayback();
            handoffToUser();
            return;
          }

          playbackWatchTimer = window.setTimeout(tick, 250);
        };
        playbackWatchTimer = window.setTimeout(tick, 250);
      };

      armGuard(networkGuardMs);

      if (!normalized) {
        handoffToUser();
        return;
      }

      try {
        const controller = new AbortController();
        const ttsTimeout = window.setTimeout(() => controller.abort(), TTS_FETCH_TIMEOUT_MS);
        const response = await (async () => {
          try {
            return await fetch("/api/tts", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ text: normalized }),
              signal: controller.signal,
            });
          } finally {
            window.clearTimeout(ttsTimeout);
          }
        })();

        if (speakSeq !== speakRequestSeqRef.current) return;
        if (!response.ok) {
          throw new Error(`TTS failed(${response.status})`);
        }

        const blob = await withTimeout(
          response.blob(),
          Math.min(TTS_BLOB_TIMEOUT_MS, networkGuardMs + 8_000),
          "TTS stream timed out. Returning to listening mode."
        );
        if (speakSeq !== speakRequestSeqRef.current) return;

        const playbackGuardMs = computeTtsPlaybackGuardMs(normalized, blob.size);
        armGuard(playbackGuardMs);

        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        currentAudioRef.current = audio;
        currentAudioUrlRef.current = url;

        audio.onended = () => {
          if (speakSeq !== speakRequestSeqRef.current) return;
          closePlayback();
          handoffToUser();
        };

        audio.onpause = () => {
          if (speakSeq !== speakRequestSeqRef.current) return;
          if (audio.currentTime <= 0.15) return;
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
        startPlaybackWatchdog(audio);

        // Let the avatar simulate lipsync for the audio duration
        // We use playbackGuardMs bounds but usually audio.duration is better if available
        let durationMs = playbackGuardMs;
        if (Number.isFinite(audio.duration) && audio.duration > 0) {
          durationMs = audio.duration * 1000;
        }
        avatarRef.current?.startSpeaking(durationMs); // Call startSpeaking once here

        if (audio.ended) {
          closePlayback();
          handoffToUser();
        }
      } catch (err) {
        if (speakSeq !== speakRequestSeqRef.current) return;
        console.error("[VoiceInterview] TTS failed:", err);
        setError(err instanceof Error ? err.message : "TTS failed.");
        closePlayback();
        handoffToUser();
      }
    },
    [closePlayback, stopListeningCapture, tryStartListening]
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

    // Immediately handoff to the parent so the GeneratingReportScreen can take over and do the API call.
    onComplete(sid);
    finishingRef.current = false;
  }, [closeAll, onComplete]);

  useEffect(() => {
    finishInterviewRef.current = () => {
      void finishInterview();
    };
  }, [finishInterview]);

  useEffect(() => {
    let cancelled = false;

    const startSession = async () => {
      if (!avatarReady) return;
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

    if (avatarReady) {
      void startSession();
    }

    return () => {
      cancelled = true;
      if (avatarReady) {
        closedRef.current = true;
        hasStartedRef.current = false;
        closeAll();
      }
    };
  }, [closeAll, initialSessionId, jobTitle, avatarReady]);

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
        animate={{
          opacity: 1,
          scale: 1,
          boxShadow: userVoiceLevel > 0.05
            ? `0 0 ${20 + userVoiceLevel * 40}px ${userVoiceLevel * 10}px rgba(59, 130, 246, ${0.4 + userVoiceLevel * 0.4})`
            : "0px 0px 0px 0px rgba(59, 130, 246, 0)"
        }}
        transition={{
          opacity: { duration: 0.6 },
          scale: { duration: 0.6 },
          boxShadow: { duration: 0.1 }
        }}
        className="relative h-64 w-64 md:h-80 md:w-80 lg:h-96 lg:w-96 rounded-full bg-white/5 border border-white/10"
      >
        <div className="absolute inset-0 rounded-full overflow-hidden">
          <TalkingAvatar ref={avatarRef} onReady={() => setAvatarReady(true)} />
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.25 }}
        className="mt-6 flex flex-col items-center gap-2"
      >
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${isListening || isAssistantSpeaking ? "bg-green-400" : "bg-foreground/35"}`}
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
