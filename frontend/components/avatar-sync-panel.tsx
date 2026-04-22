"use client";

import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { createPortal } from "react-dom";

import { AvatarCue, AvatarSyncPayload } from "@/lib/types";
import type { VrmAuditOutput } from "@/components/avatar/avatar-audit";

const AvatarRenderer = dynamic(
  () => import("@/components/avatar-renderer").then((m) => m.AvatarRenderer),
  { ssr: false, loading: () => <div className="avatar-hologram" /> },
);

type AvatarSyncPanelProps = {
  cue: AvatarCue | null;
  sync: AvatarSyncPayload | null;
  loading: boolean;
  compact?: boolean;
  perceptionExpression?: string | null;
  onToggleCompact?: () => void;
  onPlaybackStateChange?: (state: {
    speakingState: "playing" | "idle";
    playbackLatencyMs?: number;
  }) => void;
};

export function AvatarSyncPanel({
  cue,
  sync,
  loading,
  compact = false,
  perceptionExpression,
  onToggleCompact,
  onPlaybackStateChange,
}: AvatarSyncPanelProps) {
  const audioRef   = useRef<HTMLAudioElement | null>(null);
  const readyAtRef = useRef<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [audit, setAudit] = useState<VrmAuditOutput | null>(null);
  const [auditCopied, setAuditCopied] = useState(false);
  const [portalTarget, setPortalTarget] = useState<HTMLElement | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    if (window.__JOI_VRM_AUDIT__) {
      setAudit(window.__JOI_VRM_AUDIT__);
    }

    const handleAudit = (event: Event) => {
      setAudit((event as CustomEvent<VrmAuditOutput>).detail);
    };

    window.addEventListener("joi-vrm-audit", handleAudit);
    return () => window.removeEventListener("joi-vrm-audit", handleAudit);
  }, []);

  useEffect(() => {
    setPortalTarget(document.body);
  }, []);

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

  const expression = playing
    ? sync?.sentiment ?? perceptionExpression ?? cue?.expression ?? "neutral"
    : perceptionExpression ?? sync?.sentiment ?? cue?.expression ?? "neutral";
  const stageState = loading ? "syncing" : sync ? "voice-linked" : "stabilized";
  const auditSummary = audit
    ? `${audit.expressions.all.length} expressions / ${audit.bones.length} bones`
    : "pending";

  async function handleCopyAudit() {
    if (!audit || typeof navigator === "undefined" || !navigator.clipboard) {
      return;
    }

    await navigator.clipboard.writeText(JSON.stringify(audit, null, 2));
    setAuditCopied(true);
    window.setTimeout(() => setAuditCopied(false), 1600);
  }

  const panel = (
    <div className={`avatar-panel${compact ? " avatar-panel-compact" : ""}`}>
      <div className="avatar-stage">
        <div className="avatar-stage-head">
          <span className="avatar-stage-kicker">Projection chamber</span>
          <div className="avatar-stage-controls">
            <span className={`avatar-stage-status ${loading ? "warn" : "ok"}`}>{stageState}</span>
            {onToggleCompact ? (
              <button
                className="button ghost avatar-mode-toggle"
                type="button"
                onClick={onToggleCompact}
                aria-label={compact ? "Restore full presence panel" : "Open mini presence mode"}
              >
                {compact ? "Full" : "Mini"}
              </button>
            ) : null}
          </div>
        </div>
        <div className="avatar-hologram-wrap">
          <AvatarRenderer
            expression={expression}
            sync={sync}
            audioRef={audioRef}
            playing={playing}
            compact={compact}
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
          <span className="avatar-stage-copy">
            {compact ? "Ambient presence mode" : "3D asset prototype staged inside the live projection chamber"}
          </span>
        </div>
      </div>

      {sync ? (
        <>
          <audio
            className={`avatar-audio${compact ? " sr-only" : ""}`}
            controls={!compact}
            ref={audioRef}
            src={sync.audio_url}
          />
          {!compact ? (
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
          ) : null}
        </>
      ) : null}

      {!compact ? (
        <details className="avatar-audit-details">
          <summary>VRM audit ({auditSummary})</summary>
          {audit ? (
            <div className="avatar-audit-grid">
              <div>
                <span>Presets</span>
                <strong>{audit.expressions.presets.length}</strong>
              </div>
              <div>
                <span>Custom</span>
                <strong>{audit.expressions.custom.length}</strong>
              </div>
              <div>
                <span>Spring bones</span>
                <strong>{audit.capabilities.hasSpringBones ? "yes" : "no"}</strong>
              </div>
              <div>
                <span>Look at</span>
                <strong>{audit.capabilities.hasLookAt ? "yes" : "no"}</strong>
              </div>
              <div className="avatar-audit-wide">
                <span>License</span>
                <strong>{String(audit.license.licenseName ?? audit.license.licenseUrl ?? "not declared")}</strong>
              </div>
              <div className="avatar-audit-wide">
                <span>Custom expressions</span>
                <strong>{audit.expressions.custom.slice(0, 6).join(", ") || "none"}</strong>
              </div>
              <button
                className="button ghost avatar-audit-copy"
                type="button"
                onClick={handleCopyAudit}
              >
                {auditCopied ? "Copied" : "Copy audit JSON"}
              </button>
            </div>
          ) : (
            <p className="avatar-audit-empty">Audit appears after the VRM model loads.</p>
          )}
        </details>
      ) : null}
    </div>
  );

  return compact && portalTarget ? createPortal(panel, portalTarget) : panel;
}
