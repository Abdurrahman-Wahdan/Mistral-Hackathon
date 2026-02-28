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

  const handleSubmit = () => {
    setScreen("analyzing");
  };

  const handleAnalyzingReady = useCallback(() => {
    setScreen("voiceChat");
  }, []);

  const handleVoiceInterviewComplete = () => {
    setScreen("interviewReview");
  };

  const handleCloseVoiceChat = () => {
    setScreen("browse");
    setSelectedJob(null);
    setCvFiles([]);
    window.scrollTo({ top: 0, behavior: "instant" });
  };

  return (
    <>
      {screen === "browse" && (
        <>
          <LiquidMetalHero
            badge="✨ Next Generation UI"
            title="Fluid Design Excellence"
            subtitle="Experience the future of web interfaces with liquid metal aesthetics that adapt, flow, and captivate. Built for modern applications that demand both beauty and performance."
            primaryCtaLabel="Get Started"
            onPrimaryCtaClick={scrollToJobs}
            features={[
              "Seamless Animations",
              "Responsive Excellence",
              "Modern Architecture"
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

      <AnimatePresence>
        {screen === "analyzing" && selectedJob && (
          <motion.div
            key="analyzing"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6 }}
          >
            <AnalyzingScreen jobTitle={selectedJob} onReady={handleAnalyzingReady} />
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {screen === "voiceChat" && selectedJob && (
          <motion.div
            key="voiceChat"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6 }}
          >
            <VoiceChatScreen
              jobTitle={selectedJob}
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
            <InterviewReviewScreen jobTitle={selectedJob} onClose={handleCloseVoiceChat} />
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
