"use client";

import { RefObject, useCallback, useEffect, useRef, useState } from "react";

import type { AvatarSyncPayload, PerceptionState } from "@/lib/types";

/**
 * 2.5D "hologram portrait" renderer — her likeness as a layered light projection
 * instead of a 3D mesh. Aligned, background-removed portrait frames (public/avatar/joi)
 * are stacked and cross-faded:
 *  - idle: an expression frame chosen from the current sentiment
 *  - speaking: viseme frames chosen from the phoneme timeline for SHAPE, gated by
 *    live audio loudness for TIMING (mouth closes on real silences, opens with the
 *    voice) so lip-sync never drifts. A minimum hold stops per-frame flicker.
 * The `.avatar-hologram` frame supplies scanlines / glow / the speaking pulse-ring.
 */

const EXPRESSIONS = [
  "neutral", "smile", "happy", "tender", "concerned", "sad", "surprised", "smirk",
] as const;
const VISEMES = ["rest", "aa", "ee", "ih", "oh", "ou", "fv", "mbp", "l"] as const;

const EXPRESSION_IMAGE: Record<string, (typeof EXPRESSIONS)[number]> = {
  neutral: "neutral",
  positive: "smile", smile: "smile", satisfied: "smile", pleased: "smile",
  happy: "happy", joy: "happy", excited: "happy",
  tender: "tender", affectionate: "tender", needy: "tender", clingy: "tender", warm: "tender",
  concern: "concerned", concerned: "concerned", stress: "concerned", anxious: "concerned", worried: "concerned",
  negative: "sad", sad: "sad", missing: "sad", sorrow: "sad", lonely: "sad",
  shock: "surprised", surprise: "surprised", surprised: "surprised", curious: "surprised",
  smirk: "smirk", playful: "smirk", amused: "smirk",
};

const PHONEME_IMAGE: Record<string, (typeof VISEMES)[number]> = {
  A: "aa", E: "ee", I: "ih", O: "oh", Oh: "oh", U: "ou",
  MB: "mbp", FV: "fv", TH: "l", S: "ee", R: "ih", L: "l", K: "aa", rest: "rest",
};

// Lip-sync tuning.
const CLOSE_THRESHOLD = 0.05;   // loudness below this → mouth closed (rest)
const SOFT_OPEN_LEVEL = 0.13;   // below this → only a small opening
const HOLD_MS = 85;             // min time an open viseme holds before changing

type LayerType = "expression" | "viseme";
const LAYERS: Array<{ id: string; type: LayerType; key: string; src: string }> = [
  ...EXPRESSIONS.map((k) => ({ id: `expression-${k}`, type: "expression" as const, key: k, src: `/avatar/joi/expr-${k}.webp` })),
  ...VISEMES.map((k) => ({ id: `viseme-${k}`, type: "viseme" as const, key: k, src: `/avatar/joi/viseme-${k}.webp` })),
];

function activePhoneme(timeline: Array<[number, string]>, t: number): string {
  let active = "rest";
  for (const [time, label] of timeline) {
    if (time > t) break;
    active = label;
  }
  return active;
}

function expressionId(expression?: string): string {
  const key = EXPRESSION_IMAGE[(expression ?? "neutral").toLowerCase()] ?? "neutral";
  return `expression-${key}`;
}

/**
 * Returns a getter for the playing clip's RMS loudness (0..1) via a Web Audio
 * analyser, or null when unavailable. Guards the one-shot MediaElementSource per
 * element and never reroutes into a suspended context (which would mute audio).
 */
function useAudioAmplitude(audioRef?: RefObject<HTMLAudioElement | null>) {
  const ref = useRef<{
    ctx: AudioContext | null;
    analyser: AnalyserNode | null;
    buf: Uint8Array<ArrayBuffer> | null;
    sources: WeakMap<HTMLAudioElement, MediaElementAudioSourceNode>;
    failed: WeakSet<HTMLAudioElement>;
  }>({ ctx: null, analyser: null, buf: null, sources: new WeakMap(), failed: new WeakSet() });

  return useCallback((): number | null => {
    const el = audioRef?.current;
    if (!el) return null;
    const s = ref.current;
    if (s.failed.has(el)) return null;
    try {
      if (!s.ctx) {
        const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
        if (!Ctx) return null;
        s.ctx = new Ctx();
        s.analyser = s.ctx.createAnalyser();
        s.analyser.fftSize = 512;
        s.analyser.connect(s.ctx.destination);
        s.buf = new Uint8Array(s.analyser.fftSize);
      }
      // Don't route a playing element into a suspended context — it would mute.
      if (s.ctx.state !== "running") {
        void s.ctx.resume();
        return null;
      }
      if (!s.sources.has(el)) {
        const src = s.ctx.createMediaElementSource(el);
        src.connect(s.analyser!);
        s.sources.set(el, src);
      }
      s.analyser!.getByteTimeDomainData(s.buf!);
      let sum = 0;
      for (let i = 0; i < s.buf!.length; i++) {
        const v = (s.buf![i] - 128) / 128;
        sum += v * v;
      }
      return Math.min(1, Math.sqrt(sum / s.buf!.length) * 2.4);
    } catch {
      s.failed.add(el); // e.g. element already sourced elsewhere → fall back to timeline
      return null;
    }
  }, [audioRef]);
}

type AvatarPortraitProps = {
  expression?: string;
  playing?: boolean;
  compact?: boolean;
  sync?: AvatarSyncPayload | null;
  audioRef?: RefObject<HTMLAudioElement | null>;
  perceptionState?: PerceptionState | null;
};

export function AvatarPortrait({
  expression,
  playing = false,
  sync,
  audioRef,
  perceptionState,
}: AvatarPortraitProps) {
  const attentive = perceptionState?.userPresent ?? false;
  const [activeId, setActiveId] = useState<string>(() => expressionId(expression));
  const getAmplitude = useAudioAmplitude(audioRef);

  useEffect(() => {
    const timeline = sync?.phoneme_timeline ?? [];

    if (playing) {
      let raf = 0;
      let smoothed = 0;
      let heldKey = "rest";
      let heldAt = 0;

      const shapeFromTimeline = (): (typeof VISEMES)[number] => {
        if (!timeline.length) return "aa";
        const t = audioRef?.current?.currentTime ?? 0;
        const shape = PHONEME_IMAGE[activePhoneme(timeline, t)] ?? "aa";
        return shape === "rest" ? "aa" : shape;
      };

      const tick = (now: number) => {
        const amp = getAmplitude();
        let target: (typeof VISEMES)[number];

        if (amp == null) {
          // No Web Audio — drive shape straight off the timeline.
          const t = audioRef?.current?.currentTime ?? 0;
          target = timeline.length ? (PHONEME_IMAGE[activePhoneme(timeline, t)] ?? "rest") : "rest";
        } else {
          smoothed = smoothed * 0.55 + amp * 0.45;
          if (smoothed < CLOSE_THRESHOLD) {
            target = "rest";
          } else {
            let shape = timeline.length ? shapeFromTimeline() : smoothed < SOFT_OPEN_LEVEL ? "ih" : "aa";
            // Tie openness to loudness: soften wide shapes when the voice is quiet.
            if (smoothed < SOFT_OPEN_LEVEL && (shape === "aa" || shape === "oh")) shape = "ih";
            target = shape;
          }
        }

        // Min-hold: close immediately, but hold open shapes to stop flicker.
        if (target !== heldKey && (target === "rest" || now - heldAt >= HOLD_MS)) {
          heldKey = target;
          heldAt = now;
          setActiveId(`viseme-${target}`);
        }
        raf = requestAnimationFrame(tick);
      };

      raf = requestAnimationFrame(tick);
      return () => cancelAnimationFrame(raf);
    }

    setActiveId(expressionId(expression));
    return undefined;
  }, [playing, sync, expression, audioRef, getAmplitude]);

  return (
    <div
      className={`avatar-hologram avatar-portrait${playing ? " speaking" : ""}${
        attentive ? " attentive" : ""
      }`}
    >
      <div className="avatar-portrait-stage">
        {LAYERS.map((layer) => (
          <img
            key={layer.id}
            className={`avatar-portrait-face avatar-portrait-face--${layer.type}`}
            data-active={activeId === layer.id}
            src={layer.src}
            alt={layer.id === "expression-neutral" ? "Joi" : ""}
            aria-hidden={layer.id === "expression-neutral" ? undefined : true}
            draggable={false}
          />
        ))}
      </div>
      <div className="avatar-portrait-tint" aria-hidden="true" />
    </div>
  );
}
