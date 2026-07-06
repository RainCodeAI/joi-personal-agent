"use client";

import { RefObject, useEffect, useState } from "react";

import type { AvatarSyncPayload, PerceptionState } from "@/lib/types";

/**
 * 2.5D "hologram portrait" renderer — her likeness as a layered light projection
 * instead of a 3D mesh. Aligned, background-removed portrait frames (public/avatar/joi)
 * are stacked and cross-faded:
 *  - idle: an expression frame chosen from the current sentiment
 *  - speaking: viseme frames flipped through from the phoneme timeline (2D lip-sync)
 * The `.avatar-hologram` frame supplies scanlines / glow / the speaking pulse-ring.
 */

const EXPRESSIONS = [
  "neutral", "smile", "happy", "tender", "concerned", "sad", "surprised", "smirk",
] as const;
const VISEMES = ["rest", "aa", "ee", "ih", "oh", "ou"] as const;

// Sentiment/expression string → expression frame.
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

// Phoneme label (from the sync timeline) → viseme frame.
const PHONEME_IMAGE: Record<string, (typeof VISEMES)[number]> = {
  A: "aa", E: "ee", I: "ih", O: "oh", Oh: "oh", U: "ou",
  MB: "rest", FV: "ih", TH: "ee", S: "ee", R: "ih", L: "ih", K: "aa", rest: "rest",
};

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

  useEffect(() => {
    const timeline = sync?.phoneme_timeline ?? [];
    if (playing && timeline.length) {
      // Speaking: drive viseme frames off the audio clock.
      let raf = 0;
      const tick = () => {
        const t = audioRef?.current?.currentTime ?? 0;
        const key = PHONEME_IMAGE[activePhoneme(timeline, t)] ?? "rest";
        setActiveId(`viseme-${key}`);
        raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
      return () => cancelAnimationFrame(raf);
    }
    // Idle: settle on the sentiment expression.
    setActiveId(expressionId(expression));
    return undefined;
  }, [playing, sync, expression, audioRef]);

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
