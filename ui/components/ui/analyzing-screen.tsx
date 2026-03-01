"use client";

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";

interface AnalyzingScreenProps {
  jobTitle: string;
  ready: boolean;
  error?: string | null;
  onRetry?: () => void;
  onBack?: () => void;
  onReady: () => void;
}

export default function AnalyzingScreen({
  jobTitle,
  ready,
  error,
  onRetry,
  onBack,
  onReady,
}: AnalyzingScreenProps) {
  const [stage, setStage] = useState(0);

  useEffect(() => {
    const t1 = setTimeout(() => setStage(1), 600);
    const t2 = setTimeout(() => setStage(2), 1800);
    const t3 = setTimeout(() => setStage(3), 3200);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, []);

  // Proceed when animation is done (stage >= 3) AND backend is ready
  useEffect(() => {
    if (stage >= 3 && ready && !error) {
      onReady();
    }
  }, [stage, ready, error, onReady]);

  return (
    <section className="fixed inset-0 z-50 flex items-center justify-center bg-black">
      <div className="flex flex-col items-center text-center px-6 max-w-2xl">
        <AnimatePresence>
          {stage >= 0 && (
            <motion.h2
              key="heading"
              initial={{ opacity: 0, filter: "blur(20px)" }}
              animate={{ opacity: 1, filter: "blur(0px)" }}
              transition={{ duration: 1.2, ease: [0.25, 0.1, 0.25, 1] }}
              className="text-3xl sm:text-4xl lg:text-5xl font-bold text-foreground mb-6"
            >
              Preparing Your AI Interviewer
            </motion.h2>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {stage >= 1 && (
            <motion.p
              key="subtitle"
              initial={{ opacity: 0, filter: "blur(16px)" }}
              animate={{ opacity: 1, filter: "blur(0px)" }}
              transition={{ duration: 1, ease: [0.25, 0.1, 0.25, 1] }}
              className="text-lg sm:text-xl text-foreground/50 mb-4"
            >
              Building a role-specific interview plan for{" "}
              <span className="text-foreground/80 font-medium">{jobTitle}</span>
            </motion.p>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {stage >= 2 && (
            <motion.p
              key="detail"
              initial={{ opacity: 0, filter: "blur(12px)" }}
              animate={{ opacity: 1, filter: "blur(0px)" }}
              transition={{ duration: 0.8, ease: [0.25, 0.1, 0.25, 1] }}
              className="text-base text-foreground/30 mb-10"
            >
              Loading question categories, interview memory, and evaluation rules...
            </motion.p>
          )}
        </AnimatePresence>

        <AnimatePresence>
          {stage >= 3 && !error && (
            <motion.div
              key="dots"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5 }}
              className="flex gap-2"
            >
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={i}
                  className="w-2 h-2 rounded-full bg-foreground/30"
                  animate={{ opacity: [0.3, 1, 0.3] }}
                  transition={{
                    duration: 1.4,
                    repeat: Infinity,
                    delay: i * 0.2,
                    ease: "easeInOut",
                  }}
                />
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {error && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-8 w-full rounded-2xl border border-red-400/30 bg-red-500/10 p-5"
          >
            <p className="text-sm text-red-100/90 mb-5">{error}</p>
            <div className="flex flex-wrap items-center justify-center gap-3">
              {onBack && (
                <Button
                  variant="outline"
                  className="border-white/20 bg-transparent text-foreground hover:bg-white/10"
                  onClick={onBack}
                >
                  Back
                </Button>
              )}
              {onRetry && (
                <Button className="bg-white text-black hover:bg-white/90" onClick={onRetry}>
                  Retry Preparation
                </Button>
              )}
            </div>
          </motion.div>
        )}
      </div>
    </section>
  );
}
