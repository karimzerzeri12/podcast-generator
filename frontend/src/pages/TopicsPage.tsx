import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  audioDownloadUrl,
  clearSession,
  episodeScriptDownloadUrl,
  generateEpisode,
  getEpisodeScript,
  getStoredStudent,
  listEpisodes,
  listTopics,
  listVoices,
} from "../api/client";
import AudioPlayer from "../components/AudioPlayer";
import FormatSelector from "../components/FormatSelector";
import JobStatus from "../components/JobStatus";
import VoiceSelector from "../components/VoiceSelector";
import { useJobPolling } from "../hooks/useJobPolling";
import { EpisodeFormat, EpisodeOut, GenerateResponse, Topic, Voice } from "../types";

const FORMAT_LABELS: Record<EpisodeFormat, string> = {
  monologue: "Monologue",
  interview: "Guest Expert Interview",
  two_host: "Two-Host Conversation",
  debate: "Debate / Steelman",
};

export default function TopicsPage() {
  const student = getStoredStudent();
  const navigate = useNavigate();

  const [topics, setTopics] = useState<Topic[]>([]);
  const [topicsError, setTopicsError] = useState<string | null>(null);
  const [selectedTopicId, setSelectedTopicId] = useState<number | null>(null);
  const [selectedChapter, setSelectedChapter] = useState<string | null>(null);

  const [voices, setVoices] = useState<Voice[]>([]);
  const [voicesError, setVoicesError] = useState<string | null>(null);

  const [format, setFormat] = useState<EpisodeFormat | null>(null);
  const [voiceId, setVoiceId] = useState<string | null>(null);
  const [voiceId2, setVoiceId2] = useState<string | null>(null);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [genError, setGenError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [episodes, setEpisodes] = useState<EpisodeOut[]>([]);
  const [episodesError, setEpisodesError] = useState<string | null>(null);
  const [openScripts, setOpenScripts] = useState<Record<number, string>>({});

  const job = useJobPolling(result?.job ?? null);

  useEffect(() => {
    if (!student) return;
    listTopics(student.course_id)
      .then(setTopics)
      .catch(() => setTopicsError("Could not load topics."));
  }, [student]);

  useEffect(() => {
    listVoices()
      .then(setVoices)
      .catch(() => setVoicesError("Could not load voices."));
  }, []);

  function reloadEpisodes() {
    listEpisodes()
      .then(setEpisodes)
      .catch(() => setEpisodesError("Could not load your episodes."));
  }

  useEffect(reloadEpisodes, []);

  useEffect(() => {
    if (job?.stage === "done") reloadEpisodes();
  }, [job?.stage]);

  function selectTopic(id: number) {
    setSelectedTopicId(id);
    setFormat(null);
    setVoiceId(null);
    setVoiceId2(null);
    setResult(null);
    setGenError(null);
  }

  // Distinct chapter labels in topic order. If any topic has a chapter, we present a
  // two-level chapter -> sub-chapter flow; otherwise a flat topic list.
  const chapters = Array.from(
    topics.reduce((set, t) => {
      if (t.chapter) set.add(t.chapter);
      return set;
    }, new Set<string>())
  );
  const grouped = chapters.length > 0;
  const visibleTopics = grouped ? topics.filter((t) => t.chapter === selectedChapter) : topics;

  function selectChapter(chapter: string) {
    setSelectedChapter(chapter);
    setSelectedTopicId(null);
    setFormat(null);
    setVoiceId(null);
    setVoiceId2(null);
    setResult(null);
    setGenError(null);
  }

  function backToChapters() {
    setSelectedChapter(null);
    setSelectedTopicId(null);
  }

  function selectFormat(f: EpisodeFormat) {
    setFormat(f);
    setVoiceId(null);
    setVoiceId2(null);
  }

  const isDialogue = format !== null && format !== "monologue";
  const voicesMismatched = isDialogue && !!voiceId2 && voiceId2 === voiceId;
  const canGenerate =
    !!format && !!voiceId && (!isDialogue || (!!voiceId2 && !voicesMismatched)) && !submitting;

  async function handleGenerate() {
    if (!canGenerate || !format || !voiceId || !selectedTopicId) return;
    setGenError(null);
    setSubmitting(true);
    try {
      const res = await generateEpisode(
        selectedTopicId,
        format,
        voiceId,
        isDialogue ? voiceId2! : ""
      );
      setResult(res);
    } catch {
      setGenError("Could not start generation. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function toggleScript(episodeId: number) {
    if (openScripts[episodeId] !== undefined) {
      setOpenScripts((prev) => {
        const next = { ...prev };
        delete next[episodeId];
        return next;
      });
      return;
    }
    try {
      const { text } = await getEpisodeScript(episodeId);
      setOpenScripts((prev) => ({ ...prev, [episodeId]: text }));
    } catch {
      setEpisodesError("Could not load that script.");
    }
  }

  function logout() {
    clearSession();
    navigate("/");
  }

  const selectedTopic = topics.find((t) => t.id === selectedTopicId) ?? null;
  const isReady = job?.stage === "done" && job.audio_cache_id != null;

  return (
    <div className="page" style={{ maxWidth: 960 }}>
      <div className="top-bar">
        <h2>Episodes</h2>
        <div>
          <span style={{ marginRight: "1rem" }}>{student?.name}</span>
          <button className="secondary" onClick={logout}>
            Log out
          </button>
        </div>
      </div>

      {topicsError && <div className="error">{topicsError}</div>}

      <div className="topics-layout">
        <div>
          {grouped && selectedChapter === null ? (
            <ul className="topic-list">
              {chapters.map((ch) => {
                const inChapter = topics.filter((t) => t.chapter === ch);
                const blurb = inChapter[0]?.chapter_description;
                const count = inChapter.length;
                return (
                  <li key={ch}>
                    <button type="button" className="topic-link" onClick={() => selectChapter(ch)}>
                      <div className="topic-title">{ch}</div>
                      <div className="topic-desc">
                        {blurb || `${count} ${count === 1 ? "sub-chapter" : "sub-chapters"}`} &rarr;
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <>
              {grouped && (
                <button type="button" className="back-link" onClick={backToChapters}>
                  &larr; All chapters
                </button>
              )}
              {grouped && selectedChapter && (
                <div className="chapter-heading">{selectedChapter}</div>
              )}
              <ul className="topic-list">
                {visibleTopics.map((t) => (
                  <li key={t.id}>
                    <button
                      type="button"
                      className={`topic-link${t.id === selectedTopicId ? " selected" : ""}`}
                      onClick={() => selectTopic(t.id)}
                    >
                      <div className="topic-title">{t.title}</div>
                      <div className="topic-desc">{t.description}</div>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>

        <div className="card">
          {!selectedTopic && (
            <p className="hint">
              {grouped
                ? "Pick a chapter, then a sub-chapter to get started."
                : "Pick a topic on the left to get started."}
            </p>
          )}

          {selectedTopic && (
            <>
              {selectedTopic.chapter && (
                <div className="chapter-badge">{selectedTopic.chapter}</div>
              )}
              <h3>{selectedTopic.title}</h3>
              <p className="topic-desc" style={{ marginTop: 0, marginBottom: "1rem" }}>
                {selectedTopic.description}
              </p>
              {voicesError && <div className="error">{voicesError}</div>}
              <FormatSelector selected={format} onSelect={selectFormat} />

              {format && (
                <VoiceSelector
                  voices={voices}
                  selected={voiceId}
                  onSelect={setVoiceId}
                  label={isDialogue ? "Speaker 1 voice" : "Voice"}
                />
              )}
              {format && isDialogue && (
                <VoiceSelector
                  voices={voices}
                  selected={voiceId2}
                  onSelect={setVoiceId2}
                  label="Speaker 2 voice"
                />
              )}
              {voicesMismatched && (
                <div className="error">Speaker 1 and Speaker 2 need different voices.</div>
              )}

              {genError && <div className="error">{genError}</div>}

              {!result && (
                <button disabled={!canGenerate} onClick={handleGenerate}>
                  {submitting ? "Starting..." : "Generate my episode"}
                </button>
              )}

              {job && !isReady && (
                <div style={{ marginTop: "1rem" }}>
                  <JobStatus job={job} />
                </div>
              )}

              {isReady && result && (
                <div style={{ marginTop: "1rem" }}>
                  <h4>Your episode is ready</h4>
                  <AudioPlayer
                    audioCacheId={job!.audio_cache_id!}
                    studentEpisodeId={result.student_episode_id}
                  />
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <div className="card" style={{ marginTop: "1.5rem" }}>
        <h3>My Episodes</h3>
        {episodesError && <div className="error">{episodesError}</div>}
        {episodes.length === 0 && !episodesError && (
          <p className="hint">No episodes generated yet.</p>
        )}
        <ul className="episode-list">
          {episodes.map((ep) => (
            <li key={ep.id} className="episode-row">
              <div className="episode-header">
                <strong>{ep.topic_title}</strong>
                <span className="hint">
                  {" "}
                  &middot; {FORMAT_LABELS[ep.format]} &middot;{" "}
                  {new Date(ep.generated_at).toLocaleString()}
                </span>
              </div>

              {ep.stage === "done" && ep.audio_cache_id != null ? (
                <>
                  <AudioPlayer audioCacheId={ep.audio_cache_id} studentEpisodeId={ep.id} />
                  <div className="episode-actions">
                    <a href={audioDownloadUrl(ep.audio_cache_id)}>Download audio</a>
                    {ep.has_script && (
                      <>
                        {" · "}
                        <a href={episodeScriptDownloadUrl(ep.id)}>Download script</a>
                        {" · "}
                        <button className="secondary" onClick={() => toggleScript(ep.id)}>
                          {openScripts[ep.id] !== undefined ? "Hide script" : "View script"}
                        </button>
                      </>
                    )}
                  </div>
                  {openScripts[ep.id] !== undefined && (
                    <pre className="script-text">{openScripts[ep.id]}</pre>
                  )}
                </>
              ) : ep.stage === "failed" ? (
                <span className="error">Generation failed.</span>
              ) : (
                <span className="hint">Still generating&hellip;</span>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
