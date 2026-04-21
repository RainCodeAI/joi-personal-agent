import * as THREE from "three";
import { VRM, VRMExpressionPresetName, VRMHumanBoneName } from "@pixiv/three-vrm";

import { VRM_Y_ROTATION } from "./avatar-constants";
import { setExpressionIfAvailable } from "./avatar-expression";

export type IdlePoseState = {
  nextBlinkAt: number;
  blinkStartedAt: number | null;
  blinkDuration: number;
  pendingDoubleBlink: boolean;
  nextGazeAt: number;
  gazeTarget: THREE.Vector2;
  gazeCurrent: THREE.Vector2;
  nextGestureAt: number;
  gestureStartedAt: number | null;
  gestureDuration: number;
  gestureKind: "none" | "softNod" | "weightShift" | "listenTilt";
};

export type PoseFrameInput = {
  motionScale: number;
  playing: boolean;
  expression: string;
};

export function createIdlePoseState(): IdlePoseState {
  return {
    nextBlinkAt: 1.2,
    blinkStartedAt: null,
    blinkDuration: 0.12,
    pendingDoubleBlink: false,
    nextGazeAt: 0.9,
    gazeTarget: new THREE.Vector2(0, 0),
    gazeCurrent: new THREE.Vector2(0, 0),
    nextGestureAt: 4.5,
    gestureStartedAt: null,
    gestureDuration: 0,
    gestureKind: "none",
  };
}

function randomBetween(min: number, max: number): number {
  return min + Math.random() * (max - min);
}

function scheduleBlink(state: IdlePoseState, elapsed: number, near: boolean): void {
  const base = near ? randomBetween(0.16, 0.34) : randomBetween(2.6, 6.2);
  state.nextBlinkAt = elapsed + base;
  state.blinkDuration = randomBetween(0.09, 0.145);
  state.pendingDoubleBlink = !near && Math.random() < 0.18;
}

function updateBlink(state: IdlePoseState, elapsed: number): number {
  if (state.blinkStartedAt === null && elapsed >= state.nextBlinkAt) {
    state.blinkStartedAt = elapsed;
  }

  if (state.blinkStartedAt === null) {
    return 0;
  }

  const progress = (elapsed - state.blinkStartedAt) / state.blinkDuration;
  if (progress >= 1) {
    state.blinkStartedAt = null;
    scheduleBlink(state, elapsed, state.pendingDoubleBlink);
    return 0;
  }

  return Math.sin(progress * Math.PI);
}

function updateGaze(state: IdlePoseState, elapsed: number, delta: number, playing: boolean): void {
  if (elapsed >= state.nextGazeAt) {
    const range = playing ? 0.055 : 0.085;
    state.gazeTarget.set(randomBetween(-range, range), randomBetween(-0.03, 0.04));
    state.nextGazeAt = elapsed + randomBetween(1.6, playing ? 3.4 : 4.8);
  }

  const t = 1 - Math.exp(-4.5 * delta);
  state.gazeCurrent.lerp(state.gazeTarget, t);
}

function updateGesture(state: IdlePoseState, elapsed: number): number {
  if (state.gestureStartedAt === null && elapsed >= state.nextGestureAt) {
    const roll = Math.random();
    state.gestureKind = roll < 0.36 ? "softNod" : roll < 0.7 ? "weightShift" : "listenTilt";
    state.gestureDuration = randomBetween(1.1, 2.3);
    state.gestureStartedAt = elapsed;
  }

  if (state.gestureStartedAt === null) {
    return 0;
  }

  const progress = (elapsed - state.gestureStartedAt) / state.gestureDuration;
  if (progress >= 1) {
    state.gestureStartedAt = null;
    state.gestureKind = "none";
    state.nextGestureAt = elapsed + randomBetween(5.5, 13.5);
    return 0;
  }

  return Math.sin(progress * Math.PI);
}

function setBoneRotation(
  vrm: VRM,
  boneName: VRMHumanBoneName,
  rotation: [number, number, number],
): void {
  const bone = vrm.humanoid.getNormalizedBoneNode(boneName);
  if (!bone) {
    return;
  }

  bone.rotation.set(rotation[0], rotation[1], rotation[2]);
}

function applyRelaxedUpperBodyPose(
  vrm: VRM,
  elapsed: number,
  motionScale: number,
  gestureAmount: number,
  gestureKind: IdlePoseState["gestureKind"],
): void {
  const armSway = Math.sin(elapsed * 0.62) * 0.018 * motionScale;
  const shoulderSway = Math.sin(elapsed * 0.52) * 0.012 * motionScale;
  const listenTilt = gestureKind === "listenTilt" ? gestureAmount * 0.035 : 0;
  const weightShift = gestureKind === "weightShift" ? gestureAmount * 0.03 : 0;

  setBoneRotation(vrm, VRMHumanBoneName.LeftShoulder, [0.04, 0.04, -0.1 + shoulderSway + weightShift]);
  setBoneRotation(vrm, VRMHumanBoneName.RightShoulder, [0.04, -0.04, 0.1 - shoulderSway + listenTilt]);
  setBoneRotation(vrm, VRMHumanBoneName.LeftUpperArm, [0.12, 0.02, -0.96 + armSway]);
  setBoneRotation(vrm, VRMHumanBoneName.RightUpperArm, [0.12, -0.02, 0.96 - armSway]);
  setBoneRotation(vrm, VRMHumanBoneName.LeftLowerArm, [0.03, 0.02, -0.24 + armSway * 0.5]);
  setBoneRotation(vrm, VRMHumanBoneName.RightLowerArm, [0.03, -0.02, 0.24 - armSway * 0.5]);
  setBoneRotation(vrm, VRMHumanBoneName.LeftHand, [0.02, 0, -0.04]);
  setBoneRotation(vrm, VRMHumanBoneName.RightHand, [0.02, 0, 0.04]);
}

export function updateVrmIdlePose(
  vrm: VRM,
  rig: THREE.Group,
  idle: IdlePoseState,
  elapsed: number,
  delta: number,
  { motionScale, playing, expression }: PoseFrameInput,
): number {
  const blinkWeight = updateBlink(idle, elapsed);
  updateGaze(idle, elapsed, delta, playing);
  const gestureAmount = updateGesture(idle, elapsed);
  const speakingBoost = playing ? 1.025 : 1;
  const concernBias = ["stress", "concern", "negative", "missing"].includes(expression) ? 0.75 : 1;
  const breathing = Math.sin(elapsed * 0.78) * 0.03 * motionScale * concernBias;
  const drift = Math.sin(elapsed * 0.2) * 0.03 * motionScale;
  const nod = idle.gestureKind === "softNod" ? gestureAmount * 0.04 : 0;
  const weightShift = idle.gestureKind === "weightShift" ? gestureAmount * 0.018 : 0;

  rig.position.y = 0.02 + breathing;
  rig.position.x = drift + weightShift;
  rig.rotation.y = VRM_Y_ROTATION + Math.sin(elapsed * 0.18) * 0.028 * motionScale;
  rig.rotation.z = Math.sin(elapsed * 0.28) * 0.01 * motionScale + weightShift * 0.3;
  rig.scale.setScalar(speakingBoost);

  const head = vrm.humanoid.getNormalizedBoneNode(VRMHumanBoneName.Head);
  const neck = vrm.humanoid.getNormalizedBoneNode(VRMHumanBoneName.Neck);
  const chest = vrm.humanoid.getNormalizedBoneNode(VRMHumanBoneName.Chest);
  const gazeX = idle.gazeCurrent.x;
  const gazeY = idle.gazeCurrent.y;

  if (head) {
    head.rotation.x = -0.045 + gazeY + nod + Math.sin(elapsed * 0.31) * 0.012 * motionScale;
    head.rotation.y = gazeX + Math.sin(elapsed * 0.23) * 0.038 * motionScale;
    head.rotation.z =
      Math.sin(elapsed * 0.2) * 0.019 * motionScale +
      (idle.gestureKind === "listenTilt" ? gestureAmount * 0.05 : 0);
  }

  if (neck) {
    neck.rotation.x = -0.018 + gazeY * 0.32 + Math.sin(elapsed * 0.29) * 0.007 * motionScale;
    neck.rotation.y = gazeX * 0.42 + Math.sin(elapsed * 0.22) * 0.02 * motionScale;
  }

  if (chest) {
    chest.rotation.x = Math.sin(elapsed * 0.78) * 0.011 * motionScale;
    chest.rotation.z = Math.sin(elapsed * 0.24) * 0.008 * motionScale + weightShift * 0.28;
  }

  applyRelaxedUpperBodyPose(vrm, elapsed, motionScale, gestureAmount, idle.gestureKind);
  setExpressionIfAvailable(vrm, VRMExpressionPresetName.Blink, blinkWeight);

  return blinkWeight;
}
