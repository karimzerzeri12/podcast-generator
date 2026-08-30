import { FormEvent, useState } from "react";
import { getEngagement, getPodcastSettings, updatePodcastSettings } from "../api/client";
import { EngagementRow, PodcastSettings } from "../types";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV ? "http://localhost:8000" : "");
const ADMIN_TOKEN_KEY = "podcast_gen_admin_token";

export default function AdminDashboardPage() {
  const [adminToken, setAdminToken] = useState(localStorage.getItem(ADMIN_TOKEN_KEY) ?? "");
  const [rows, setRows] = useState<EngagementRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [settings, setSettings] = useState<PodcastSettings | null>(null);
  const [lengthDraft, setLengthDraft] = useState(5);
  const [settingsStatus, setSettingsStatus] = useState<string | null>(null);
  const [settingsIsError, setSettingsIsError] = useState(false);
  const [savingLength, setSavingLength] = useState(false);

  const [limitDraft, setLimitDraft] = useState(0);
  const [limitStatus, setLimitStatus] = useState<string | null>(null);
  const [limitIsError, setLimitIsError] = useState(false);
  const [savingLimit, setSavingLimit] = useState(false);

  async function handleSaveLength(e: FormEvent) {
    e.preventDefault();
    if (!adminToken) return;
    setSavingLength(true);
    setSettingsStatus(null);
    try {
      const updated = await updatePodcastSettings(adminToken, {
        episode_length_minutes: lengthDraft,
      });
      setSettings(updated);
      setSettingsIsError(false);
      setSettingsStatus(`Podcast length set to ${updated.episode_length_minutes} minutes.`);
    } catch (err) {
      setSettingsIsError(true);
      setSettingsStatus(err instanceof Error ? err.message : "Could not save podcast length.");
    } finally {
      setSavingLength(false);
    }
  }

  async function handleSaveLimit(e: FormEvent) {
    e.preventDefault();
    if (!adminToken) return;
    setSavingLimit(true);
    setLimitStatus(null);
    try {
      const updated = await updatePodcastSettings(adminToken, {
        max_generations_per_student: limitDraft,
      });
      setSettings(updated);
      setLimitIsError(false);
      setLimitStatus(
        updated.max_generations_per_student === 0
          ? "Per-student limit removed (unlimited)."
          : `Each student can now generate up to ${updated.max_generations_per_student} podcasts.`
      );
    } catch (err) {
      setLimitIsError(true);
      setLimitStatus(err instanceof Error ? err.message : "Could not save the limit.");
    } finally {
      setSavingLimit(false);
    }
  }

  async function load() {
    setError(null);
    setLoading(true);
    try {
      const [data, currentSettings] = await Promise.all([
        getEngagement(adminToken),
        getPodcastSettings(adminToken),
      ]);
      setRows(data);
      setSettings(currentSettings);
      setLengthDraft(currentSettings.episode_length_minutes);
      setLimitDraft(currentSettings.max_generations_per_student);
      localStorage.setItem(ADMIN_TOKEN_KEY, adminToken);
    } catch {
      setError("Invalid admin token or server error.");
    } finally {
      setLoading(false);
    }
  }

  async function downloadCsv() {
    const resp = await fetch(`${API_BASE}/admin/engagement.csv`, {
      headers: { "X-Admin-Token": adminToken },
    });
    if (!resp.ok) {
      setError("Could not download CSV.");
      return;
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "engagement.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="page" style={{ maxWidth: 960 }}>
      <h2>Engagement Dashboard</h2>
      <div className="card">
        <input
          type="password"
          placeholder="Admin token"
          value={adminToken}
          onChange={(e) => setAdminToken(e.target.value)}
        />
        <button onClick={load} disabled={loading || !adminToken}>
          {loading ? "Loading..." : "Load engagement data"}
        </button>{" "}
        {rows.length > 0 && (
          <button className="secondary" onClick={downloadCsv}>
            Download CSV
          </button>
        )}
        {error && <div className="error">{error}</div>}
      </div>

      {settings && (
        <div className="card">
          <h3>Podcast length</h3>
          <form onSubmit={handleSaveLength}>
            <label>
              Target episode length: <strong>{lengthDraft} minutes</strong>
              <input
                type="range"
                min={settings.min_minutes}
                max={settings.max_minutes}
                step={1}
                value={lengthDraft}
                onChange={(e) => setLengthDraft(Number(e.target.value))}
              />
            </label>
            <button type="submit" disabled={savingLength || lengthDraft === settings.episode_length_minutes}>
              {savingLength ? "Saving..." : "Save length"}
            </button>
            {settingsStatus && (
              <div className={settingsIsError ? "error" : "success"}>{settingsStatus}</div>
            )}
          </form>
          <p className="hint">
            Applies to newly generated episodes going forward (range: {settings.min_minutes}-
            {settings.max_minutes} minutes). Existing cached scripts/audio aren't deleted — if you
            change this back later, previously generated episodes at that length are served again
            instead of regenerating.
          </p>
        </div>
      )}

      {settings && (
        <div className="card">
          <h3>Per-student generation limit</h3>
          <form onSubmit={handleSaveLimit}>
            <label>
              Max podcasts each student can generate:{" "}
              <input
                type="number"
                min={0}
                max={settings.max_generations_cap}
                step={1}
                value={limitDraft}
                onChange={(e) => setLimitDraft(Number(e.target.value))}
                style={{ width: 100 }}
              />
            </label>
            <button
              type="submit"
              disabled={savingLimit || limitDraft === settings.max_generations_per_student}
            >
              {savingLimit ? "Saving..." : "Save limit"}
            </button>
            {limitStatus && (
              <div className={limitIsError ? "error" : "success"}>{limitStatus}</div>
            )}
          </form>
          <p className="hint">
            Set to <strong>0</strong> for unlimited. Counts each podcast a student generates (a
            student who hits the limit can still listen to and download episodes they already
            generated — they just can't create new ones). Lowering the limit never deletes anything
            already generated.
          </p>
        </div>
      )}

      {rows.length > 0 && (
        <div className="card" style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Student</th>
                <th>Topic</th>
                <th>Format</th>
                <th>Voice(s)</th>
                <th>Generated</th>
                <th>Listened (s)</th>
                <th>Completion</th>
                <th>Last played</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td>
                    {r.student_name}
                    <br />
                    <small>{r.student_email}</small>
                  </td>
                  <td>{r.topic_title}</td>
                  <td>{r.format}</td>
                  <td>{r.voice_id_2 ? `${r.voice_id} + ${r.voice_id_2}` : r.voice_id}</td>
                  <td>{new Date(r.generated_at).toLocaleString()}</td>
                  <td>{Math.round(r.total_listened_seconds)}</td>
                  <td>{r.completion_pct}%</td>
                  <td>{r.last_played_at ? new Date(r.last_played_at).toLocaleString() : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
