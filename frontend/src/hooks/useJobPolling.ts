import { useEffect, useState } from "react";
import { getJob } from "../api/client";
import { JobOut } from "../types";

const POLL_INTERVAL_MS = 2_500;
const TERMINAL_STAGES = new Set(["done", "failed"]);

export function useJobPolling(initialJob: JobOut | null): JobOut | null {
  const [job, setJob] = useState<JobOut | null>(initialJob);

  useEffect(() => {
    setJob(initialJob);
    if (!initialJob || TERMINAL_STAGES.has(initialJob.stage)) return;

    let cancelled = false;
    const interval = window.setInterval(async () => {
      try {
        const updated = await getJob(initialJob.id);
        if (cancelled) return;
        setJob(updated);
        if (TERMINAL_STAGES.has(updated.stage)) {
          window.clearInterval(interval);
        }
      } catch {
        // transient network error — keep polling on the next tick
      }
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [initialJob?.id]);

  return job;
}
