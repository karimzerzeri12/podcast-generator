import type {
  EngagementRow,
  EpisodeFormat,
  EpisodeOut,
  GenerateResponse,
  JobOut,
  PodcastSettings,
  Student,
  Topic,
  Voice,
} from "../types";

// Empty string => same-origin (relative URLs). Used for the bundled/deployed build where
// the frontend is served from the same host as the API (tunnel, Docker, VM). Only local
// Vite dev (two separate ports) needs the explicit localhost:8000, hence the DEV branch.
// An explicit VITE_API_BASE_URL still wins if set to a non-empty value.
const API_BASE =
  import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? "http://localhost:8000" : "");
const TOKEN_KEY = "podcast_gen_token";
const STUDENT_KEY = "podcast_gen_student";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredStudent(): Student | null {
  const raw = localStorage.getItem(STUDENT_KEY);
  return raw ? (JSON.parse(raw) as Student) : null;
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(STUDENT_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${body}`);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export async function login(email: string, access_code: string): Promise<Student> {
  const data = await request<{ token: string; student: Student }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, access_code }),
  });
  localStorage.setItem(TOKEN_KEY, data.token);
  localStorage.setItem(STUDENT_KEY, JSON.stringify(data.student));
  return data.student;
}

export function listTopics(courseId: number): Promise<Topic[]> {
  return request(`/courses/${courseId}/topics`);
}

export function listVoices(): Promise<Voice[]> {
  return request("/voices");
}

export function generateEpisode(
  topicId: number,
  format: EpisodeFormat,
  voiceId: string,
  voiceId2: string = ""
): Promise<GenerateResponse> {
  return request("/generate", {
    method: "POST",
    body: JSON.stringify({
      topic_id: topicId,
      format,
      voice_id: voiceId,
      voice_id_2: voiceId2,
    }),
  });
}

export function getJob(jobId: number): Promise<JobOut> {
  return request(`/jobs/${jobId}`);
}

export function audioStreamUrl(audioCacheId: number): string {
  return `${API_BASE}/audio/${audioCacheId}/stream?token=${encodeURIComponent(getToken() ?? "")}`;
}

export function audioDownloadUrl(audioCacheId: number): string {
  return `${API_BASE}/audio/${audioCacheId}/download?token=${encodeURIComponent(getToken() ?? "")}`;
}

export function listEpisodes(): Promise<EpisodeOut[]> {
  return request("/episodes");
}

export function getEpisodeScript(episodeId: number): Promise<{ text: string }> {
  return request(`/episodes/${episodeId}/script`);
}

export function episodeScriptDownloadUrl(episodeId: number): string {
  return `${API_BASE}/episodes/${episodeId}/script/download?token=${encodeURIComponent(getToken() ?? "")}`;
}

export function postListeningEvent(
  studentEpisodeId: number,
  eventType: string,
  positionSeconds: number
): Promise<void> {
  return request("/listening-events", {
    method: "POST",
    body: JSON.stringify({
      student_episode_id: studentEpisodeId,
      event_type: eventType,
      position_seconds: positionSeconds,
      client_timestamp: new Date().toISOString(),
    }),
  });
}

export async function getEngagement(adminToken: string): Promise<EngagementRow[]> {
  const resp = await fetch(`${API_BASE}/admin/engagement`, {
    headers: { "X-Admin-Token": adminToken },
  });
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  return resp.json();
}

export async function getPodcastSettings(adminToken: string): Promise<PodcastSettings> {
  const resp = await fetch(`${API_BASE}/admin/settings`, {
    headers: { "X-Admin-Token": adminToken },
  });
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  return resp.json();
}

export async function updatePodcastSettings(
  adminToken: string,
  update: { episode_length_minutes?: number; max_generations_per_student?: number }
): Promise<PodcastSettings> {
  const resp = await fetch(`${API_BASE}/admin/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", "X-Admin-Token": adminToken },
    body: JSON.stringify(update),
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${body}`);
  }
  return resp.json();
}

