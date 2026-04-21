import type { RefObject } from "react";
import { VRMExpressionPresetName } from "@pixiv/three-vrm";

import type { AvatarSyncPayload } from "@/lib/types";

import type { ExpressionWeights } from "./avatar-expression";
import { smoothWeights } from "./avatar-expression";

export const VRM_VISEME_NAMES = [
  VRMExpressionPresetName.Aa,
  VRMExpressionPresetName.Ih,
  VRMExpressionPresetName.Ou,
  VRMExpressionPresetName.Ee,
  VRMExpressionPresetName.Oh,
];

const PHONEME_TO_VISEME: Record<string, ExpressionWeights> = {
  A: { [VRMExpressionPresetName.Aa]: 0.82, [VRMExpressionPresetName.Oh]: 0.12 },
  E: { [VRMExpressionPresetName.Ee]: 0.72, [VRMExpressionPresetName.Ih]: 0.18 },
  I: { [VRMExpressionPresetName.Ih]: 0.72, [VRMExpressionPresetName.Ee]: 0.14 },
  O: { [VRMExpressionPresetName.Oh]: 0.78, [VRMExpressionPresetName.Aa]: 0.12 },
  Oh: { [VRMExpressionPresetName.Oh]: 0.82 },
  U: { [VRMExpressionPresetName.Ou]: 0.76, [VRMExpressionPresetName.Oh]: 0.14 },
  MB: {},
  FV: { [VRMExpressionPresetName.Ih]: 0.12 },
  TH: { [VRMExpressionPresetName.Ee]: 0.14 },
  S: { [VRMExpressionPresetName.Ee]: 0.12 },
  R: { [VRMExpressionPresetName.Ih]: 0.1 },
  L: { [VRMExpressionPresetName.Ih]: 0.14, [VRMExpressionPresetName.Ee]: 0.1 },
  K: { [VRMExpressionPresetName.Aa]: 0.08 },
  rest: {},
};

function activePhoneme(timeline: Array<[number, string]>, currentTime: number): string {
  let active = "rest";

  for (const [time, label] of timeline) {
    if (time > currentTime) {
      break;
    }
    active = label;
  }

  return active;
}

export function getSpeechTargets(
  sync: AvatarSyncPayload | null,
  audioRef: RefObject<HTMLAudioElement | null>,
  playing: boolean,
): ExpressionWeights {
  if (!playing || !sync?.phoneme_timeline.length) {
    return {};
  }

  const currentTime = audioRef.current?.currentTime ?? 0;
  const label = activePhoneme(sync.phoneme_timeline, currentTime);
  return PHONEME_TO_VISEME[label] ?? {};
}

export function smoothSpeechWeights(
  current: ExpressionWeights,
  target: ExpressionWeights,
  delta: number,
): ExpressionWeights {
  const targetHasMouthOpen = Object.values(target).some((value) => value > 0.05);
  return smoothWeights(current, target, delta, targetHasMouthOpen ? 20 : 12);
}
