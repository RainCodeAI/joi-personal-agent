import * as THREE from "three";

export type AvatarAssetKind = "vrm" | "glb";

export const ACTIVE_AVATAR_ASSET: AvatarAssetKind =
  process.env.NEXT_PUBLIC_JOI_AVATAR_ASSET === "glb" ? "glb" : "vrm";
export const VRM_MODEL_URL = "/avatar/models/vroid-joi/joi-vroid-v1.vrm";
export const GLB_MODEL_URL = "/avatar/models/ai-girllike-it/source/009-3.glb";
export const USE_VRM_MODEL = ACTIVE_AVATAR_ASSET === "vrm";

export function isVrmAsset(assetKind: AvatarAssetKind): boolean {
  return assetKind === "vrm";
}

export const CA_OFFSET = new THREE.Vector2(0.0016, 0.0016);
export const GLB_TARGET_HEIGHT = 3.3;
export const GLB_VERTICAL_OFFSET = 0.98;
export const VRM_TARGET_HEIGHT = 4.5;
export const VRM_FLOOR_OFFSET = -1.38;
export const VRM_BUST_GROUP_OFFSET = new THREE.Vector3(0, 0.72, 0);
export const GLB_BUST_GROUP_OFFSET = new THREE.Vector3(0, 0, 0);
export const VRM_VISIBLE_LOOK_AT = new THREE.Vector3(0, 2.22, 0);
export const GLB_VISIBLE_LOOK_AT = new THREE.Vector3(0, 1.48, 0);
export const VRM_CAMERA_POSITION = new THREE.Vector3(0, 2.24, 6.18);
export const GLB_CAMERA_POSITION = new THREE.Vector3(0, 1.36, 4.72);
export const VRM_CAMERA_FOV = 34;
export const GLB_CAMERA_FOV = 32;
export const VRM_COMPACT_VISIBLE_LOOK_AT = new THREE.Vector3(0, 2.14, 0);
export const GLB_COMPACT_VISIBLE_LOOK_AT = new THREE.Vector3(0, 1.76, 0);
export const VRM_COMPACT_CAMERA_POSITION = new THREE.Vector3(0, 2.18, 5.35);
export const GLB_COMPACT_CAMERA_POSITION = new THREE.Vector3(0, 1.74, 4.35);
export const VRM_COMPACT_CAMERA_FOV = 32;
export const GLB_COMPACT_CAMERA_FOV = 31;
export const GLB_Y_ROTATION = -Math.PI / 2;
export const VRM_Y_ROTATION = 0;

export type AvatarCameraConfig = {
  fov: number;
  lookAt: THREE.Vector3;
  position: THREE.Vector3;
};

export function getAvatarCameraConfig(
  assetKind: AvatarAssetKind,
  compact = false,
): AvatarCameraConfig {
  const isVrm = isVrmAsset(assetKind);

  if (compact) {
    return {
      fov: isVrm ? VRM_COMPACT_CAMERA_FOV : GLB_COMPACT_CAMERA_FOV,
      lookAt: isVrm ? VRM_COMPACT_VISIBLE_LOOK_AT : GLB_COMPACT_VISIBLE_LOOK_AT,
      position: isVrm ? VRM_COMPACT_CAMERA_POSITION : GLB_COMPACT_CAMERA_POSITION,
    };
  }

  return {
    fov: isVrm ? VRM_CAMERA_FOV : GLB_CAMERA_FOV,
    lookAt: isVrm ? VRM_VISIBLE_LOOK_AT : GLB_VISIBLE_LOOK_AT,
    position: isVrm ? VRM_CAMERA_POSITION : GLB_CAMERA_POSITION,
  };
}

export const MOTION_SCALE: Record<string, number> = {
  whisper: 0.55,
  intense: 1.35,
  hesitant: 0.72,
  stressed: 0.82,
  normal: 1,
};

export const EXPRESSION_TINT: Record<
  string,
  { key: string; fill: string; rim: string; accent: string }
> = {
  neutral: { key: "#91d6ff", fill: "#a8efff", rim: "#ff93c9", accent: "#7ef2ff" },
  positive: { key: "#91f0ff", fill: "#c5fff3", rim: "#ffb27a", accent: "#80f5ff" },
  smile: { key: "#91f0ff", fill: "#c5fff3", rim: "#ffb27a", accent: "#80f5ff" },
  satisfied: { key: "#91f0ff", fill: "#c5fff3", rim: "#ffb27a", accent: "#80f5ff" },
  stress: { key: "#8fc7ff", fill: "#8bd1ff", rim: "#ff7b88", accent: "#ffb36b" },
  concern: { key: "#8fc7ff", fill: "#8bd1ff", rim: "#ff7b88", accent: "#ffb36b" },
  negative: { key: "#8fc7ff", fill: "#8bd1ff", rim: "#ff7b88", accent: "#ffb36b" },
  needy: { key: "#8ed9ff", fill: "#a8ecff", rim: "#ff86b7", accent: "#ffb36b" },
  clingy: { key: "#8ed9ff", fill: "#a8ecff", rim: "#ff86b7", accent: "#ffb36b" },
  shock: { key: "#b0ebff", fill: "#d9f9ff", rim: "#ffd083", accent: "#ffb36b" },
  surprise: { key: "#b0ebff", fill: "#d9f9ff", rim: "#ffd083", accent: "#ffb36b" },
  missing: { key: "#73bfe8", fill: "#8fd0e8", rim: "#ff7b88", accent: "#7ef2ff" },
  smirk: { key: "#93e8ff", fill: "#bcf1ff", rim: "#ff9ac0", accent: "#ffb36b" },
};
