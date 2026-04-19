"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";

import { AvatarCue, AvatarSyncPayload } from "@/lib/types";

// Three.js requires browser APIs — exclude from SSR entirely
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
  const audioRef    = useRef<HTMLAudioElement | null>(null);
  const readyAtRef  = useRef<number | null>(null);
  const [playing, setPlaying] = useState(false);

  // Track when a new sync payload arrives so we can measure playback latency
  useEffect(() => {
    setPlaying(false);
    readyAtRef.current =
      typeof performance !== "undefined" ? performance.now() : null;
  }, [sync?.audio_url]);

  // Auto-play when audio_url changes
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !sync?.audio_url) return;
    audio.currentTime = 0;
    void audio.play().catch(() => {
      // Autoplay blocked — controls remain for manual playback.
    });
  }, [sync?.audio_url]);

  // Wire play/pause/ended to external playback state callback
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

    audio.addEventListener("play",   handlePlay);
    audio.addEventListener("pause",  handlePause);
    audio.addEventListener("ended",  handleEnded);
    return () => {
      audio.removeEventListener("play",   handlePlay);
      audio.removeEventListener("pause",  handlePause);
      audio.removeEventListener("ended",  handleEnded);
    };
  }, [onPlaybackStateChange]);

  // Priority: active TTS sentiment > perception expression > avatar cue > neutral
  const expression = sync?.sentiment ?? perceptionExpression ?? cue?.expression ?? "neutral";

  return (
    <section className="panel hero-card">
      <p className="eyebrow">Hologram</p>
      <h3>Joi</h3>

      <AvatarRenderer
        expression={expression}
        sync={sync}
        audioRef={audioRef}
        playing={playing}
      />

      <div className="avatar-meta">
        <span className="badge">{cue?.voice_hint ?? "default"}</span>
        <span className="badge">{expression}</span>
        <span className={`badge ${loading ? "warn" : "ok"}`}>
          {loading ? "syncing" : "ready"}
        </span>
      </div>

      {sync ? (
        <>
          <audio
            controls
            ref={audioRef}
            src={sync.audio_url}
            style={{ width: "100%", marginTop: 18 }}
          />
          <div className="viseme-track">
            {sync.phoneme_timeline.slice(0, 18).map(([time, label], index) => (
              <div className="viseme-chip" key={`${time}-${label}-${index}`}>
                <strong>{label}</strong>
                <span>{time.toFixed(2)}s</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="empty-state">No avatar sync payload yet.</div>
      )}
    </section>
  );
}
