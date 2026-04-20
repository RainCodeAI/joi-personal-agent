"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";

import { AvatarCue, AvatarSyncPayload } from "@/lib/types";

const AvatarRenderer = dynamic(
  () => import("@/components/avatar-renderer").then((m) => m.AvatarRenderer),
  { ssr: false, loading: () => <div className="avatar-hologram" /> },
);

type AvatarSyncPanelProps = {
  cue: AvatarCue | null;
  sync: AvatarSyncPayload | null;
  loading: boolean;
  perceptionExpression?: string | null;
  onPlaybackStateChange?: (state: {
    speakingState: "playing" | "idle";
    playbackLatencyMs?: number;
  }) => void;
};

export function AvatarSyncPanel({
  cue,
  sync,
  loading,
  perceptionExpression,
  onPlaybackStateChange,
}: AvatarSyncPanelProps) {
  const audioRef   = useRef<HTMLAudioElement | null>(null);
  const readyAtRef = useRef<number | null>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    setPlaying(false);
    readyAtRef.current =
      typeof performance !== "undefined" ? performance.now() : null;
  }, [sync?.audio_url]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !sync?.audio_url) return;
    audio.currentTime = 0;
    void audio.play().catch(() => {});
  }, [sync?.audio_url]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handlePlay = () => {
      setPlaying(true);
      const playbackLatencyMs = readyAtRef.current
        ? Math.max(0, Math.round(performance.now() - readyAtRef.current))
        : undefined;
      onPlaybackStateChange?.({ speakingState: "playing", playbackLatencyMs });
    };
    const handlePause = () => {
      setPlaying(false);
      onPlaybackStateChange?.({ speakingState: "idle" });
    };
    const handleEnded = () => {
      setPlaying(false);
      onPlaybackStateChange?.({ speakingState: "idle" });
    };

    audio.addEventListener("play",  handlePlay);
    audio.addEventListener("pause", handlePause);
    audio.addEventListener("ended", handleEnded);
    return () => {
      audio.removeEventListener("play",  handlePlay);
      audio.removeEventListener("pause", handlePause);
      audio.removeEventListener("ended", handleEnded);
    };
  }, [onPlaybackStateChange]);

  const expression = sync?.sentiment ?? perceptionExpression ?? cue?.expression ?? "neutral";
  const stageState = loading ? "syncing" : sync ? "voice-linked" : "stabilized";

  return (
    <div className="avatar-panel">
      <div className="avatar-stage">
        <div className="avatar-stage-head">
          <span className="avatar-stage-kicker">Projection chamber</span>
          <span className={`avatar-stage-status ${loading ? "warn" : "ok"}`}>{stageState}</span>
        </div>
        <div className="avatar-hologram-wrap">
          <AvatarRenderer
            expression={expression}
            sync={sync}
            audioRef={audioRef}
            playing={playing}
          />
          <div className="avatar-badges-overlay">
            <span className="badge avatar-badge">{cue?.voice_hint ?? "default"}</span>
            <span className="badge avatar-badge">{expression}</span>
            <span className={`badge avatar-badge ${loading ? "warn" : "ok"}`}>
              {loading ? "syncing" : "ready"}
            </span>
          </div>
        </div>
        <div className="avatar-stage-base">
          <span className="avatar-stage-name">Joi</span>
          <span className="avatar-stage-copy">3D asset prototype staged inside the live projection chamber</span>
        </div>
      </div>

      {sync ? (
        <>
          <audio
            className="avatar-audio"
            controls
            ref={audioRef}
            src={sync.audio_url}
          />
          <details className="viseme-details">
            <summary>Phoneme track ({sync.phoneme_timeline.length} frames)</summary>
            <div className="viseme-track">
              {sync.phoneme_timeline.slice(0, 18).map(([time, label], index) => (
                <div className="viseme-chip" key={`${time}-${label}-${index}`}>
                  <strong>{label}</strong>
                  <span>{(time as number).toFixed(2)}s</span>
                </div>
              ))}
            </div>
          </details>
        </>
      ) : null}
    </div>
  );
}
