"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface Job {
  title: string;
  description: string;
  skills: string[];
}

const jobs: Job[] = [
  {
    title: "Software Engineer",
    description:
      "Design, develop, and maintain scalable software systems. Collaborate with cross-functional teams to deliver high-quality products.",
    skills: ["JavaScript", "React", "Node.js", "System Design"],
  },
  {
    title: "Data Scientist",
    description:
      "Analyze complex datasets to extract insights and build predictive models. Drive data-informed decision making across the organization.",
    skills: ["Python", "Machine Learning", "SQL", "Statistics"],
  },
  {
    title: "Product Manager",
    description:
      "Define product vision and strategy. Prioritize features, coordinate with engineering, and ensure products meet user needs.",
    skills: ["Strategy", "User Research", "Roadmapping", "Analytics"],
  },
  {
    title: "UX Designer",
    description:
      "Create intuitive and delightful user experiences. Conduct research, build prototypes, and iterate based on user feedback.",
    skills: ["Figma", "Prototyping", "User Testing", "Design Systems"],
  },
  {
    title: "DevOps Engineer",
    description:
      "Build and maintain CI/CD pipelines, infrastructure, and monitoring systems. Ensure reliability and scalability of production environments.",
    skills: ["AWS", "Docker", "Kubernetes", "Terraform"],
  },
  {
    title: "Marketing Manager",
    description:
      "Develop and execute marketing strategies to drive growth. Manage campaigns, analyze performance, and optimize conversion funnels.",
    skills: ["SEO", "Content Strategy", "Analytics", "Brand"],
  },
];

interface JobsListProps {
  onApply?: (jobTitle: string) => void;
}

export default function JobsList({ onApply }: JobsListProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [isVisible, setIsVisible] = useState(false);

  const sectionRef = useRef<HTMLElement>(null);
  const isScrollingBack = useRef(false);
  const isScrollingToApply = useRef(false);

  const handleBack = () => {
    isScrollingBack.current = true;
    setSelectedIndex(null);
    setExpandedIndex(null);
    setIsVisible(false);
    setTimeout(() => {
      document.getElementById("hero")?.scrollIntoView({ behavior: "smooth" });
      setTimeout(() => {
        isScrollingBack.current = false;
      }, 1000);
    }, 50);
  };

  const toggle = (index: number) => {
    if (selectedIndex === index) {
      setSelectedIndex(null);
      setExpandedIndex(null);
    } else {
      setExpandedIndex(index);
      setSelectedIndex(index);
    }
  };

  useEffect(() => {
    const handleScroll = () => {
      if (isScrollingBack.current || isScrollingToApply.current) return;
      const section = sectionRef.current;
      if (!section) return;
      const rect = section.getBoundingClientRect();
      const visibleHeight = Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0);
      const ratio = visibleHeight / rect.height;
      setIsVisible(ratio > 0.3);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <section
      ref={sectionRef}
      id="jobs"
      className="relative min-h-screen flex items-center justify-center py-24 px-6"
    >
      <div className="w-full max-w-2xl space-y-3">
        {jobs.map((job, index) => {
          const isSelected = selectedIndex === index;
          return (
            <motion.div
              key={job.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: index * 0.08 }}
            >
              <button
                onClick={() => toggle(index)}
                style={isSelected ? { outline: "2px solid rgba(255,255,255,0.5)", outlineOffset: "-2px" } : undefined}
                className={`w-full text-left rounded-xl backdrop-blur-2xl transition-all duration-300 overflow-hidden ${
                  isSelected
                    ? "bg-white/[0.07] shadow-[0_0_20px_rgba(255,255,255,0.1)]"
                    : "bg-white/[0.04] hover:bg-white/[0.07]"
                }`}
              >
                <div className="flex items-center justify-between px-6 py-5">
                  <span className="text-lg font-medium text-foreground">
                    {job.title}
                  </span>
                  <motion.span
                    animate={{ rotate: expandedIndex === index ? 45 : 0 }}
                    transition={{ duration: 0.2 }}
                    className="text-foreground/50 text-xl"
                  >
                    +
                  </motion.span>
                </div>

                <AnimatePresence initial={false}>
                  {expandedIndex === index && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{
                        duration: 0.3,
                        ease: [0.25, 0.1, 0.25, 1],
                      }}
                      className="overflow-hidden"
                    >
                      <div className="px-6 pb-5 space-y-3">
                        <p className="text-foreground/70 text-sm leading-relaxed">
                          {job.description}
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {job.skills.map((skill) => (
                            <Badge
                              key={skill}
                              variant="secondary"
                              className="bg-foreground/10 text-foreground/80 border-foreground/15 text-xs"
                            >
                              {skill}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </button>
            </motion.div>
          );
        })}
      </div>

      <AnimatePresence>
        {isVisible && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="fixed bottom-8 left-8 z-50"
          >
            <Button
              size="lg"
              variant="outline"
              className="group h-auto border-white/20 text-foreground hover:bg-white/10 transition-all duration-300 backdrop-blur-xl text-base px-6 py-4 font-semibold rounded-xl overflow-hidden"
              onClick={handleBack}
            >
              <span className="relative block">
                <span className="block transition-opacity duration-300 group-hover:opacity-0">Back</span>
                <span className="absolute inset-0 flex items-center justify-center text-xl opacity-0 transition-opacity duration-300 group-hover:opacity-100">&larr;</span>
              </span>
            </Button>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {selectedIndex !== null && isVisible && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
            className="fixed bottom-8 right-8 z-50"
          >
            <Button
              size="lg"
              className="group h-auto bg-white text-black hover:bg-white/90 transition-all duration-300 shadow-2xl text-base px-6 py-4 font-semibold rounded-xl overflow-hidden"
              onClick={() => {
                if (onApply && selectedIndex !== null) {
                  isScrollingToApply.current = true;
                  setIsVisible(false);
                  onApply(jobs[selectedIndex].title);
                  setTimeout(() => {
                    isScrollingToApply.current = false;
                  }, 1500);
                }
              }}
            >
              <span className="relative block">
                <span className="block transition-opacity duration-300 group-hover:opacity-0">Apply</span>
                <span className="absolute inset-0 flex items-center justify-center text-xl opacity-0 transition-opacity duration-300 group-hover:opacity-100">&rarr;</span>
              </span>
            </Button>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
