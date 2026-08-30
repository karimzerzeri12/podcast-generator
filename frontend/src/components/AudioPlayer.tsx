import { useEffect, useRef } from "react";
import { audioStreamUrl, postListeningEvent } from "../api/client";

const HEARTBEAT_INTERVAL_MS = 15_000;

interface Props {
  audioCacheId: number;
  studentEpisodeId: number;
}

export default function AudioPlayer({ audioCacheId, studentEpisodeId }: Props) {
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const send = (eventType: string) =>
      postListeningEvent(studentEpisodeId, eventType, audio.currentTime).catch(() => {
        /* best-effort telemetry, non-fatal */
      });

    let heartbeatTimer: number | undefined;
    const onPlay = () => {
      send("play");
      heartbeatTimer = window.setInterval(() => send("heartbeat"), HEARTBEAT_INTERVAL_MS);
    };
    const onPauseOrEnded = (eventType: string) => () => {
      window.clearInterval(heartbeatTimer);
      send(eventType);
    };
    const onSeeked = () => send("seek");

    const onPause = onPauseOrEnded("pause");
    const onEnded = onPauseOrEnded("ended");

    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("ended", onEnded);
    audio.addEventListener("seeked", onSeeked);

    return () => {
      window.clearInterval(heartbeatTimer);
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("seeked", onSeeked);
    };
  }, [studentEpisodeId]);

  return (
    <audio
      ref={audioRef}
      controls
      style={{ width: "100%" }}
      src={audioStreamUrl(audioCacheId)}
    />
  );
}
