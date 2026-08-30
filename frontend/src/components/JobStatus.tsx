import { JobOut } from "../types";

const STAGE_LABELS: Record<string, string> = {
  queued: "Queued...",
  generating_script: "Writing your episode script...",
  synthesizing_audio: "Recording the audio...",
  done: "Ready!",
  failed: "Generation failed.",
};

export default function JobStatus({ job }: { job: JobOut }) {
  return (
    <div>
      <div>{STAGE_LABELS[job.stage] ?? job.stage}</div>
      <div className="progress-bar">
        <div className="progress-bar-fill" style={{ width: `${job.progress_pct}%` }} />
      </div>
      {job.stage === "failed" && job.error_message && (
        <div className="error">{job.error_message}</div>
      )}
    </div>
  );
}
