export type EpisodeFormat = "monologue" | "interview" | "two_host" | "debate";

export type JobStage =
  | "queued"
  | "generating_script"
  | "synthesizing_audio"
  | "done"
  | "failed";

export interface Student {
  id: number;
  name: string;
  email: string;
  course_id: number;
}

export interface Topic {
  id: number;
  title: string;
  order_index: number;
  description: string;
  chapter: string;
  chapter_description: string;
}

export interface Voice {
  id: string;
  name: string;
  description: string;
  preview_url: string | null;
}

export interface JobOut {
  id: number;
  stage: JobStage;
  progress_pct: number;
  error_message: string;
  audio_cache_id: number | null;
}

export interface GenerateResponse {
  cache_hit: boolean;
  job: JobOut;
  student_episode_id: number;
}

export type ListeningEventType = "play" | "pause" | "heartbeat" | "seek" | "ended";

export interface EngagementRow {
  student_id: number;
  student_name: string;
  student_email: string;
  topic_id: number;
  topic_title: string;
  format: EpisodeFormat;
  voice_id: string;
  voice_id_2: string;
  generated_at: string;
  total_listened_seconds: number;
  completion_pct: number;
  last_played_at: string | null;
}

export interface PodcastSettings {
  episode_length_minutes: number;
  min_minutes: number;
  max_minutes: number;
  max_generations_per_student: number;
  max_generations_cap: number;
}

export interface EpisodeOut {
  id: number;
  topic_id: number;
  topic_title: string;
  format: EpisodeFormat;
  voice_id: string;
  voice_id_2: string;
  generated_at: string;
  stage: JobStage;
  audio_cache_id: number | null;
  has_script: boolean;
}
