"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import LiquidMetalHero from '@/components/ui/liquid-metal-hero';
import JobsList from '@/components/ui/jobs-list';
import CvUploadSection from '@/components/ui/cv-upload-section';
import AnalyzingScreen from '@/components/ui/analyzing-screen';
import VoiceChatScreen from '@/components/ui/voice-chat-screen';
import InterviewReviewScreen from '@/components/ui/interview-review-screen';
import { UploadedFile } from '@/components/ui/file-upload-card';

type Screen = "browse" | "analyzing" | "voiceChat" | "interviewReview";

export default function Home() {
  const [selectedJob, setSelectedJob] = useState<string | null>(null);
  const [cvFiles, setCvFiles] = useState<UploadedFile[]>([]);
  const [screen, setScreen] = useState<Screen>("browse");
  const [interviewSessionId, setInterviewSessionId] = useState<string | null>(null);
  const [preparedSessionId, setPreparedSessionId] = useState<string | null>(null);
  const [isApiReady, setIsApiReady] = useState(false);
  const [prepareError, setPrepareError] = useState<string | null>(null);
  const isNavigatingBackRef = useRef(false);
  const backTimeoutRef = useRef<number | null>(null);
  const scrollRafRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (backTimeoutRef.current !== null) {
        window.clearTimeout(backTimeoutRef.current);
      }
      if (scrollRafRef.current !== null) {
        window.cancelAnimationFrame(scrollRafRef.current);
      }
    };
  }, []);

  const scrollToSection = (sectionId: string) => {
    document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const scrollToJobs = () => {
    scrollToSection("jobs");
  };

  const animateScrollTo = useCallback((targetY: number, durationMs: number, onDone: () => void) => {
    if (scrollRafRef.current !== null) {
      window.cancelAnimationFrame(scrollRafRef.current);
      scrollRafRef.current = null;
    }

    const startY = window.scrollY;
    const distance = targetY - startY;
    if (Math.abs(distance) < 2) {
      onDone();
      return;
    }

    const startTime = performance.now();
    const easeInOutQuad = (t: number) =>
      t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

    const step = (now: number) => {
      const progress = Math.min((now - startTime) / durationMs, 1);
      const eased = easeInOutQuad(progress);
      window.scrollTo(0, startY + distance * eased);

      if (progress < 1) {
        scrollRafRef.current = window.requestAnimationFrame(step);
        return;
      }

      scrollRafRef.current = null;
      onDone();
    };

    scrollRafRef.current = window.requestAnimationFrame(step);
  }, []);

  const handleApply = (jobTitle: string) => {
    setSelectedJob(jobTitle);
    setTimeout(() => {
      const el = document.getElementById("cv-upload");
      if (el) {
        window.scrollTo({ top: el.offsetTop, behavior: "smooth" });
      }
    }, 300);
  };

  const handleBackToJobs = () => {
    if (isNavigatingBackRef.current) return;
    const jobsEl = document.getElementById("jobs");
    if (!jobsEl) {
      return;
    }

    isNavigatingBackRef.current = true;
    if (backTimeoutRef.current !== null) {
      window.clearTimeout(backTimeoutRef.current);
      backTimeoutRef.current = null;
    }

    let finalized = false;
    const finalize = () => {
      if (finalized) return;
      finalized = true;
      if (backTimeoutRef.current !== null) {
        window.clearTimeout(backTimeoutRef.current);
        backTimeoutRef.current = null;
      }
      isNavigatingBackRef.current = false;
    };

    // Force an actual animated scroll and keep selection/upload state persistent.
    animateScrollTo(jobsEl.offsetTop, 620, finalize);
    backTimeoutRef.current = window.setTimeout(finalize, 900);
  };

  const runPreparation = useCallback(async () => {
    const cvFile = cvFiles.find((f) => f.status === "completed")?.file ?? null;
    if (!selectedJob || !cvFile) {
      setPrepareError("Please select a role and upload a valid CV before starting.");
      return;
    }

    setPreparedSessionId(null);
    setIsApiReady(false);
    setInterviewSessionId(null);
    setPrepareError(null);
    setScreen("analyzing");

    try {
      const formData = new FormData();
      formData.append("file", cvFile);
      formData.append("job_title", selectedJob);
      const res = await fetch("/api/prepare-session", { method: "POST", body: formData });

      if (!res.ok) {
        const payload = (await res.json().catch(() => null)) as { detail?: string; error?: string } | null;
        const details = payload?.detail ?? payload?.error ?? `HTTP ${res.status}`;
        throw new Error(`Preparation failed: ${details}`);
      }

      const data = (await res.json()) as { session_id?: string };
      const sessionId = (data.session_id ?? "").trim();
      if (!sessionId) {
        throw new Error("Preparation failed: missing session id.");
      }
      setPreparedSessionId(sessionId);
      setIsApiReady(true);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Preparation failed. Please try again.";
      setPrepareError(message);
      setIsApiReady(false);
    }
  }, [cvFiles, selectedJob]);

  const handleSubmit = useCallback(() => {
    void runPreparation();
  }, [runPreparation]);

  const handleAnalyzingRetry = useCallback(() => {
    void runPreparation();
  }, [runPreparation]);

  const handleAnalyzingBack = useCallback(() => {
    setScreen("browse");
    setIsApiReady(false);
    setPrepareError(null);
  }, []);

  const handleAnalyzingReady = useCallback(() => {
    if (!preparedSessionId) {
      setPrepareError("Preparation is not complete yet. Please retry.");
      return;
    }
    setScreen("voiceChat");
  }, [preparedSessionId]);

  const handleVoiceInterviewComplete = (sessionId: string | null) => {
    setInterviewSessionId(sessionId);
    setScreen("interviewReview");
  };

  const handleCloseVoiceChat = () => {
    setScreen("browse");
    setInterviewSessionId(null);
    setPreparedSessionId(null);
    setIsApiReady(false);
    setPrepareError(null);
    setSelectedJob(null);
    setCvFiles([]);
    window.scrollTo({ top: 0, behavior: "instant" });
  };

  return (
    <>
      {screen === "browse" && (
        <>
          <LiquidMetalHero
            badge="AI Interviewer Platform"
            title="Practice Interviews with an AI Hiring Team"
            subtitle="Select a role, upload your CV, and run a realistic voice interview powered by your own agent stack. Receive a structured report with strengths, gaps, and next-step coaching."
            primaryCtaLabel="Start"
            onPrimaryCtaClick={scrollToJobs}
            features={[
              "Role-Specific Questions",
              "Live AI Interview Flow",
              "Actionable Performance Review"
            ]}
          />
          <JobsList onApply={handleApply} />
          {selectedJob && (
            <CvUploadSection
              jobTitle={selectedJob}
              files={cvFiles}
              setFiles={setCvFiles}
              onBack={handleBackToJobs}
              onSubmit={handleSubmit}
            />
          )}
        </>
      )}

      {screen === "analyzing" && selectedJob && (
        <AnalyzingScreen
          jobTitle={selectedJob}
          ready={isApiReady}
          error={prepareError}
          onRetry={handleAnalyzingRetry}
          onBack={handleAnalyzingBack}
          onReady={handleAnalyzingReady}
        />
      )}

      <AnimatePresence>
        {screen === "voiceChat" && selectedJob && preparedSessionId && (
          <motion.div
            key="voiceChat"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6 }}
          >
            <VoiceChatScreen
              jobTitle={selectedJob}
              initialSessionId={preparedSessionId}
              onClose={handleCloseVoiceChat}
              onComplete={handleVoiceInterviewComplete}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {screen === "interviewReview" && selectedJob && (
          <motion.div
            key="interviewReview"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6 }}
          >
            <InterviewReviewScreen
              jobTitle={selectedJob}
              sessionId={interviewSessionId}
              onClose={handleCloseVoiceChat}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
