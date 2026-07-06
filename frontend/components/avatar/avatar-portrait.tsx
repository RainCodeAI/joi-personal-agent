"use client";

import type { PerceptionState } from "@/lib/types";

/**
 * 2.5D "hologram portrait" renderer — her likeness as a layered light projection
 * instead of a 3D mesh. Uses the generated reference portraits (public/avatar/joi)
 * composited inside the existing `.avatar-hologram` frame (scanlines + glow + the
 * speaking pulse-ring all come from the shared CSS). Idle drift + a speaking
 * brightness lift sell "she's present" without a 3D rig.
 *
 * Follow-ups (need matching-framing art or bg-removed cutouts): expression swaps
 * and 2D viseme lip-sync via the dormant `.avatar-layer--mouth` overlay path.
 */

const PORTRAIT_NEUTRAL = "/avatar/joi/portrait-neutral.png";

type AvatarPortraitProps = {
  expression?: string;
  playing?: boolean;
  compact?: boolean;
  perceptionState?: PerceptionState | null;
};

export function AvatarPortrait({ playing = false, perceptionState }: AvatarPortraitProps) {
  const attentive = perceptionState?.userPresent ?? false;

  return (
    <div
      className={`avatar-hologram avatar-portrait${playing ? " speaking" : ""}${
        attentive ? " attentive" : ""
      }`}
    >
      <div className="avatar-portrait-stage">
        <img
          className="avatar-portrait-face"
          src={PORTRAIT_NEUTRAL}
          alt="Joi"
          draggable={false}
        />
      </div>
      <div className="avatar-portrait-tint" aria-hidden="true" />
    </div>
  );
}
