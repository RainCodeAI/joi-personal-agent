import * as THREE from "three";
import { VRM, VRMExpressionPresetName } from "@pixiv/three-vrm";

export type ExpressionWeights = Record<string, number>;

const EXPRESSION_ALIASES: Record<string, ExpressionWeights> = {
  neutral: {
    [VRMExpressionPresetName.Relaxed]: 0.18,
  },
  positive: {
    [VRMExpressionPresetName.Happy]: 0.42,
    [VRMExpressionPresetName.Relaxed]: 0.12,
  },
  smile: {
    [VRMExpressionPresetName.Happy]: 0.5,
    [VRMExpressionPresetName.Relaxed]: 0.08,
  },
  satisfied: {
    [VRMExpressionPresetName.Happy]: 0.46,
    [VRMExpressionPresetName.Relaxed]: 0.16,
  },
  smirk: {
    [VRMExpressionPresetName.Happy]: 0.34,
    [VRMExpressionPresetName.Relaxed]: 0.16,
  },
  concern: {
    [VRMExpressionPresetName.Sad]: 0.34,
    [VRMExpressionPresetName.Relaxed]: 0.08,
  },
  stress: {
    [VRMExpressionPresetName.Sad]: 0.4,
    [VRMExpressionPresetName.Angry]: 0.08,
  },
  negative: {
    [VRMExpressionPresetName.Sad]: 0.36,
    [VRMExpressionPresetName.Relaxed]: 0.06,
  },
  needy: {
    [VRMExpressionPresetName.Sad]: 0.24,
    [VRMExpressionPresetName.Relaxed]: 0.14,
  },
  clingy: {
    [VRMExpressionPresetName.Sad]: 0.3,
    [VRMExpressionPresetName.Relaxed]: 0.1,
  },
  missing: {
    [VRMExpressionPresetName.Sad]: 0.32,
    [VRMExpressionPresetName.Relaxed]: 0.08,
  },
  shock: {
    [VRMExpressionPresetName.Surprised]: 0.5,
  },
  surprise: {
    [VRMExpressionPresetName.Surprised]: 0.5,
  },
};

export const FACIAL_EXPRESSION_NAMES = Array.from(
  new Set(Object.values(EXPRESSION_ALIASES).flatMap((weights) => Object.keys(weights))),
);

export function setExpressionIfAvailable(vrm: VRM, name: string, value: number): void {
  const expressionManager = vrm.expressionManager;
  if (!expressionManager?.getExpression(name)) {
    return;
  }

  expressionManager.setValue(name, THREE.MathUtils.clamp(value, 0, 1));
}

export function getExpressionTargets(expression: string, playing: boolean): ExpressionWeights {
  const key = expression.toLowerCase();
  const base = EXPRESSION_ALIASES[key] ?? EXPRESSION_ALIASES.neutral;
  const speechSoftening = playing ? 0.88 : 1;

  return Object.fromEntries(
    Object.entries(base).map(([name, value]) => [name, value * speechSoftening]),
  );
}

export function smoothWeights(
  current: ExpressionWeights,
  target: ExpressionWeights,
  delta: number,
  speed: number,
): ExpressionWeights {
  const names = new Set([...Object.keys(current), ...Object.keys(target)]);
  const t = 1 - Math.exp(-speed * delta);
  const next: ExpressionWeights = {};

  for (const name of names) {
    const value = THREE.MathUtils.lerp(current[name] ?? 0, target[name] ?? 0, t);
    if (value > 0.001) {
      next[name] = value;
    }
  }

  return next;
}

export function applyExpressionWeights(vrm: VRM, weights: ExpressionWeights): void {
  for (const [name, value] of Object.entries(weights)) {
    setExpressionIfAvailable(vrm, name, value);
  }
}
