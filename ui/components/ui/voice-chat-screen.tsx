"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { VoicePoweredOrb } from "@/components/ui/voice-powered-orb";
import { Button } from "@/components/ui/button";

interface VoiceChatScreenProps {
  jobTitle: string;
  onClose: () => void;
  onComplete: () => void;
}

export default function VoiceChatScreen({ jobTitle, onClose, onComplete }: VoiceChatScreenProps) {
  const [voiceDetected, setVoiceDetected] = useState(false);

  return (
    <section className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black">
      <motion.p
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.3 }}
        className="absolute top-12 text-foreground/30 text-sm font-medium tracking-wide"
      >
        Interview Practice — {jobTitle}
      </motion.p>

      <motion.div
        initial={{ opacity: 0, scale: 0.8 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.8, ease: [0.25, 0.1, 0.25, 1] }}
        className="w-72 h-72 sm:w-96 sm:h-96 relative"
      >
        <VoicePoweredOrb
          enableVoiceControl={true}
          className="rounded-full overflow-hidden"
          onVoiceDetected={setVoiceDetected}
        />
      </motion.div>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: voiceDetected ? 0.6 : 0.25 }}
        transition={{ duration: 0.3 }}
        className="mt-8 text-foreground text-sm"
      >
        {voiceDetected ? "Listening..." : "Start speaking to begin your interview"}
      </motion.p>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.6 }}
        className="fixed bottom-8 left-8 z-50"
      >
        <Button
          size="lg"
          variant="outline"
          className="group h-auto border-white/20 text-foreground hover:bg-white/10 transition-all duration-300 backdrop-blur-xl text-base px-6 py-4 font-semibold rounded-xl overflow-hidden"
          onClick={onClose}
        >
          <span className="relative block">
            <span className="block transition-opacity duration-300 group-hover:opacity-0">Close</span>
            <span className="absolute inset-0 flex items-center justify-center text-xl opacity-0 transition-opacity duration-300 group-hover:opacity-100">&times;</span>
          </span>
        </Button>
      </motion.div>

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.5, delay: 0.6 }}
        className="fixed bottom-8 right-8 z-50"
      >
        <Button
          size="lg"
          className="group h-auto bg-white text-black hover:bg-white/90 transition-all duration-300 shadow-2xl text-base px-6 py-4 font-semibold rounded-xl overflow-hidden"
          onClick={onComplete}
        >
          <span className="relative block">
            <span className="block transition-opacity duration-300 group-hover:opacity-0">Finish Interview</span>
            <span className="absolute inset-0 flex items-center justify-center opacity-0 transition-opacity duration-300 group-hover:opacity-100">
              <svg
                aria-hidden="true"
                viewBox="0 0 24 24"
                className="h-5 w-5"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.25"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M20 6L9 17l-5-5" />
              </svg>
            </span>
          </span>
        </Button>
      </motion.div>
    </section>
  );
}
