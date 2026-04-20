"use client";

import { Suspense, useEffect, useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { Canvas, useFrame, useLoader, useThree } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import {
  Bloom,
  ChromaticAberration,
  EffectComposer,
  Noise,
  Vignette,
} from "@react-three/postprocessing";
import { BlendFunction } from "postprocessing";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import {
  VRM,
  VRMExpressionPresetName,
  VRMHumanBoneName,
  VRMLoaderPlugin,
} from "@pixiv/three-vrm";

import { AvatarSyncPayload } from "@/lib/types";

const ACTIVE_AVATAR_ASSET: "vrm" | "glb" = "vrm";
const VRM_MODEL_URL = "/avatar/models/vroid-joi/joi-vroid-v1.vrm";
const GLB_MODEL_URL = "/avatar/models/ai-girllike-it/source/009-3.glb";
const USE_VRM_MODEL = ACTIVE_AVATAR_ASSET === "vrm";
const CA_OFFSET = new THREE.Vector2(0.0022, 0.0022);
const GLB_TARGET_HEIGHT = 3.3;
const GLB_VERTICAL_OFFSET = 0.98;
const VRM_TARGET_HEIGHT = 4.5;
const VRM_FLOOR_OFFSET = -1.38;
const VISIBLE_LOOK_AT = new THREE.Vector3(0, 1.58, 0);
const GLB_Y_ROTATION = -Math.PI / 2;
const VRM_Y_ROTATION = 0;

const MOTION_SCALE: Record<string, number> = {
  whisper: 0.55,
  intense: 1.35,
  hesitant: 0.72,
  stressed: 0.82,
  normal: 1,
};

const EXPRESSION_TINT: Record<
  string,
  { key: string; fill: string; rim: string; accent: string }
> = {
  neutral: { key: "#8ed9ff", fill: "#9fe8ff", rim: "#ff93c9", accent: "#7ef2ff" },
  positive: { key: "#8ef7ff", fill: "#b8fff0", rim: "#ffb06f", accent: "#7ef2ff" },
  smile: { key: "#8ef7ff", fill: "#b8fff0", rim: "#ffb06f", accent: "#7ef2ff" },
  satisfied: { key: "#8ef7ff", fill: "#b8fff0", rim: "#ffb06f", accent: "#7ef2ff" },
  stress: { key: "#90d0ff", fill: "#86c9ff", rim: "#ff7b88", accent: "#ffb36b" },
  concern: { key: "#90d0ff", fill: "#86c9ff", rim: "#ff7b88", accent: "#ffb36b" },
  negative: { key: "#90d0ff", fill: "#86c9ff", rim: "#ff7b88", accent: "#ffb36b" },
  needy: { key: "#8ed9ff", fill: "#9fe8ff", rim: "#ff86b7", accent: "#ffb36b" },
  clingy: { key: "#8ed9ff", fill: "#9fe8ff", rim: "#ff86b7", accent: "#ffb36b" },
  shock: { key: "#b0ebff", fill: "#d0f7ff", rim: "#ffd083", accent: "#ffb36b" },
  missing: { key: "#73bfe8", fill: "#84cde8", rim: "#ff7b88", accent: "#7ef2ff" },
  smirk: { key: "#93e8ff", fill: "#bcf1ff", rim: "#ff9ac0", accent: "#ffb36b" },
};

useGLTF.preload(GLB_MODEL_URL);

function buildHaloTexture(): THREE.CanvasTexture {
  const size = 512;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("2D context unavailable");
  }

  const gradient = ctx.createRadialGradient(
    size / 2,
    size / 2,
    size * 0.22,
    size / 2,
    size / 2,
    size * 0.5,
  );
  gradient.addColorStop(0, "rgba(126, 242, 255, 0)");
  gradient.addColorStop(0.55, "rgba(126, 242, 255, 0.08)");
  gradient.addColorStop(1, "rgba(255, 123, 136, 0.22)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);

  return new THREE.CanvasTexture(canvas);
}

function buildAtmosphereTexture(): THREE.CanvasTexture {
  const width = 512;
  const height = 768;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    throw new Error("2D context unavailable");
  }

  const background = ctx.createLinearGradient(0, 0, 0, height);
  background.addColorStop(0, "rgba(8,14,24,0.04)");
  background.addColorStop(0.45, "rgba(10,18,32,0.24)");
  background.addColorStop(1, "rgba(3,7,14,0.05)");
  ctx.fillStyle = background;
  ctx.fillRect(0, 0, width, height);

  const crownGlow = ctx.createRadialGradient(
    width * 0.5,
    height * 0.24,
    0,
    width * 0.5,
    height * 0.24,
    width * 0.36,
  );
  crownGlow.addColorStop(0, "rgba(126,242,255,0.28)");
  crownGlow.addColorStop(0.54, "rgba(126,242,255,0.1)");
  crownGlow.addColorStop(1, "rgba(126,242,255,0)");
  ctx.fillStyle = crownGlow;
  ctx.fillRect(0, 0, width, height);

  const lowerFog = ctx.createRadialGradient(
    width * 0.5,
    height * 0.82,
    0,
    width * 0.5,
    height * 0.82,
    width * 0.48,
  );
  lowerFog.addColorStop(0, "rgba(255,123,136,0.12)");
  lowerFog.addColorStop(0.62, "rgba(126,242,255,0.08)");
  lowerFog.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = lowerFog;
  ctx.fillRect(0, 0, width, height);

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

function CameraRig() {
  const { camera, gl } = useThree();

  useEffect(() => {
    gl.toneMapping = THREE.ACESFilmicToneMapping;
    gl.toneMappingExposure = USE_VRM_MODEL ? 0.58 : 0.82;
    camera.lookAt(VISIBLE_LOOK_AT);
    camera.updateProjectionMatrix();
  }, [camera, gl]);

  useFrame(() => {
    camera.lookAt(VISIBLE_LOOK_AT);
  });

  return null;
}

type ModelProps = {
  expression: string;
  deliveryStyle: string;
  playing: boolean;
};

function getBlinkWeight(elapsed: number): number {
  const blinkCycle = elapsed % 4.8;
  if (blinkCycle > 0.1) {
    return 0;
  }

  return Math.sin((blinkCycle / 0.1) * Math.PI);
}

function getMoodExpression(expression: string): string | null {
  if (["positive", "smile", "satisfied", "smirk"].includes(expression)) {
    return VRMExpressionPresetName.Happy;
  }

  if (["stress", "concern", "negative", "missing", "needy", "clingy"].includes(expression)) {
    return VRMExpressionPresetName.Sad;
  }

  if (expression === "shock") {
    return VRMExpressionPresetName.Surprised;
  }

  return VRMExpressionPresetName.Relaxed;
}

function setExpressionIfAvailable(vrm: VRM, name: string, value: number): void {
  const expressionManager = vrm.expressionManager;
  if (!expressionManager?.getExpression(name)) {
    return;
  }

  expressionManager.setValue(name, THREE.MathUtils.clamp(value, 0, 1));
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

function applyRelaxedUpperBodyPose(vrm: VRM, elapsed: number, motionScale: number): void {
  const armSway = Math.sin(elapsed * 0.62) * 0.018 * motionScale;
  const shoulderSway = Math.sin(elapsed * 0.52) * 0.012 * motionScale;

  setBoneRotation(vrm, VRMHumanBoneName.LeftShoulder, [0.04, 0.04, -0.1 + shoulderSway]);
  setBoneRotation(vrm, VRMHumanBoneName.RightShoulder, [0.04, -0.04, 0.1 - shoulderSway]);
  setBoneRotation(vrm, VRMHumanBoneName.LeftUpperArm, [0.12, 0.02, -0.96 + armSway]);
  setBoneRotation(vrm, VRMHumanBoneName.RightUpperArm, [0.12, -0.02, 0.96 - armSway]);
  setBoneRotation(vrm, VRMHumanBoneName.LeftLowerArm, [0.03, 0.02, -0.24 + armSway * 0.5]);
  setBoneRotation(vrm, VRMHumanBoneName.RightLowerArm, [0.03, -0.02, 0.24 - armSway * 0.5]);
  setBoneRotation(vrm, VRMHumanBoneName.LeftHand, [0.02, 0, -0.04]);
  setBoneRotation(vrm, VRMHumanBoneName.RightHand, [0.02, 0, 0.04]);
}

function auditVrm(vrm: VRM): void {
  const expressionManager = vrm.expressionManager;
  const expressionKeys = Object.keys(expressionManager?.expressionMap ?? {});
  const presetKeys = Object.keys(expressionManager?.presetExpressionMap ?? {});
  const customKeys = Object.keys(expressionManager?.customExpressionMap ?? {});
  const boneKeys = Object.keys(vrm.humanoid.humanBones ?? {});

  console.info("[Joi avatar] VRM loaded", {
    meta: vrm.meta,
    expressionKeys,
    presetKeys,
    customKeys,
    boneKeys,
    hasLookAt: Boolean(vrm.lookAt),
    hasSpringBones: Boolean(vrm.springBoneManager),
  });
}

function useVrm(url: string): VRM | null {
  const gltf = useLoader(GLTFLoader, url, (loader) => {
    loader.register((parser) => new VRMLoaderPlugin(parser));
  });

  return (gltf.userData.vrm as VRM | undefined) ?? null;
}

function VrmBust({ expression, deliveryStyle, playing }: ModelProps) {
  const vrm = useVrm(VRM_MODEL_URL);
  const rigRef = useRef<THREE.Group>(null);
  const loggedRef = useRef(false);

  useEffect(() => {
    if (!vrm || loggedRef.current) {
      return;
    }

    auditVrm(vrm);
    loggedRef.current = true;
  }, [vrm]);

  useLayoutEffect(() => {
    if (!vrm) {
      return;
    }

    const model = vrm.scene;
    const bounds = new THREE.Box3().setFromObject(model);
    const size = bounds.getSize(new THREE.Vector3());
    const center = bounds.getCenter(new THREE.Vector3());
    const scale = VRM_TARGET_HEIGHT / Math.max(size.y, 0.001);

    model.scale.setScalar(scale);
    model.position.set(-center.x * scale, -bounds.min.y * scale + VRM_FLOOR_OFFSET, -center.z * scale);
    model.rotation.set(0, 0, 0);

    model.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (!mesh.isMesh) {
        return;
      }

      mesh.castShadow = false;
      mesh.receiveShadow = false;
      mesh.frustumCulled = false;

      const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      for (const material of materials) {
        if (!material) continue;
        material.needsUpdate = true;
      }
    });
  }, [vrm]);

  useFrame((state, delta) => {
    if (!vrm || !rigRef.current) {
      return;
    }

    const elapsed = state.clock.elapsedTime;
    const motionScale = MOTION_SCALE[deliveryStyle] ?? 1;
    const speakingBoost = playing ? 1.03 : 1;
    const breathing = Math.sin(elapsed * 0.8) * 0.032 * motionScale;
    const drift = Math.sin(elapsed * 0.21) * 0.034 * motionScale;
    const head = vrm.humanoid.getNormalizedBoneNode(VRMHumanBoneName.Head);
    const neck = vrm.humanoid.getNormalizedBoneNode(VRMHumanBoneName.Neck);
    const chest = vrm.humanoid.getNormalizedBoneNode(VRMHumanBoneName.Chest);

    rigRef.current.position.y = 0.02 + breathing;
    rigRef.current.position.x = drift;
    rigRef.current.rotation.y = VRM_Y_ROTATION + Math.sin(elapsed * 0.18) * 0.035 * motionScale;
    rigRef.current.rotation.z = Math.sin(elapsed * 0.28) * 0.012 * motionScale;
    rigRef.current.scale.setScalar(speakingBoost);

    if (head) {
      head.rotation.x = -0.045 + Math.sin(elapsed * 0.33) * 0.018 * motionScale;
      head.rotation.y = Math.sin(elapsed * 0.25) * 0.065 * motionScale;
      head.rotation.z = Math.sin(elapsed * 0.2) * 0.026 * motionScale;
    }

    if (neck) {
      neck.rotation.x = -0.018 + Math.sin(elapsed * 0.29) * 0.008 * motionScale;
      neck.rotation.y = Math.sin(elapsed * 0.22) * 0.026 * motionScale;
    }

    if (chest) {
      chest.rotation.x = Math.sin(elapsed * 0.8) * 0.012 * motionScale;
      chest.rotation.z = Math.sin(elapsed * 0.24) * 0.01 * motionScale;
    }

    applyRelaxedUpperBodyPose(vrm, elapsed, motionScale);

    const expressionManager = vrm.expressionManager;
    if (expressionManager) {
      expressionManager.resetValues();
      setExpressionIfAvailable(vrm, VRMExpressionPresetName.Blink, getBlinkWeight(elapsed));
      setExpressionIfAvailable(vrm, getMoodExpression(expression) ?? VRMExpressionPresetName.Relaxed, 0.34);
      setExpressionIfAvailable(
        vrm,
        VRMExpressionPresetName.Aa,
        playing ? 0.14 + Math.max(0, Math.sin(elapsed * 8.2)) * 0.24 : 0.015,
      );
    }

    vrm.update(delta);
  });

  if (!vrm) {
    return null;
  }

  return (
    <group ref={rigRef}>
      <primitive object={vrm.scene} />
    </group>
  );
}

function StaticGlbBust({ deliveryStyle, playing }: ModelProps) {
  const { scene } = useGLTF(GLB_MODEL_URL);
  const model = scene;
  const rigRef = useRef<THREE.Group>(null);

  useLayoutEffect(() => {
    const bounds = new THREE.Box3().setFromObject(model);
    const size = bounds.getSize(new THREE.Vector3());
    const center = bounds.getCenter(new THREE.Vector3());
    const scale = GLB_TARGET_HEIGHT / Math.max(size.y, 0.001);

    model.position.set(-center.x, -center.y + GLB_VERTICAL_OFFSET, -center.z);
    model.scale.setScalar(scale);

    model.traverse((child) => {
      const mesh = child as THREE.Mesh;
      if (!mesh.isMesh) {
        return;
      }
      mesh.castShadow = false;
      mesh.receiveShadow = false;

      const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      for (const material of materials) {
        if (!material) continue;
        material.side = THREE.DoubleSide;
        material.needsUpdate = true;
      }
    });
  }, [model]);

  useFrame((state, delta) => {
    if (!rigRef.current) {
      return;
    }

    const elapsed = state.clock.elapsedTime;
    const motionScale = MOTION_SCALE[deliveryStyle] ?? 1;
    const speakingBoost = playing ? 1.24 : 1;
    const breathing = Math.sin(elapsed * 0.86) * 0.038 * motionScale;
    const settle = Math.sin(elapsed * 0.26) * 0.024 * motionScale;

    rigRef.current.position.y = -0.22 + breathing;
    rigRef.current.position.x = Math.sin(elapsed * 0.21) * 0.045 * motionScale;
    rigRef.current.rotation.y =
      GLB_Y_ROTATION - 0.08 + Math.sin(elapsed * 0.23) * 0.06 * motionScale;
    rigRef.current.rotation.x = -0.02 + Math.sin(elapsed * 0.33) * 0.014 * motionScale;
    rigRef.current.rotation.z = settle;

    const pulse = 1 + Math.sin(elapsed * 0.86) * 0.004 * motionScale;
    const emphasis = 1 + (playing ? Math.sin(elapsed * 3.8) * 0.01 : 0);
    const scale = pulse * emphasis * speakingBoost;
    rigRef.current.scale.setScalar(scale);
  });

  return (
    <group ref={rigRef}>
      <primitive object={model} />
    </group>
  );
}

function ModelBust(props: ModelProps) {
  if (ACTIVE_AVATAR_ASSET === "vrm") {
    return <VrmBust {...props} />;
  }

  return <StaticGlbBust {...props} />;
}

type SceneProps = {
  expression: string;
  deliveryStyle: string;
  playing: boolean;
};

function HologramScene({ expression, deliveryStyle, playing }: SceneProps) {
  const ringRef = useRef<THREE.Group>(null);
  const haloMatRef = useRef<THREE.MeshBasicMaterial>(null);
  const atmosphereTex = useMemo(() => buildAtmosphereTexture(), []);
  const haloTex = useMemo(() => buildHaloTexture(), []);
  const colors = EXPRESSION_TINT[expression] ?? EXPRESSION_TINT.neutral;

  useFrame((state, delta) => {
    const elapsed = state.clock.elapsedTime;

    if (ringRef.current) {
      ringRef.current.rotation.z += delta * 0.1;
      ringRef.current.rotation.y = Math.sin(elapsed * 0.15) * 0.18;
      ringRef.current.position.y = -0.08 + Math.sin(elapsed * 0.34) * 0.05;
    }

    if (haloMatRef.current) {
      haloMatRef.current.opacity = THREE.MathUtils.lerp(
        haloMatRef.current.opacity,
        playing ? 0.8 : 0.55,
        1 - Math.exp(-4 * delta),
      );
      haloMatRef.current.color.set(colors.accent);
    }
  });

  return (
    <>
      <CameraRig />

      <ambientLight intensity={USE_VRM_MODEL ? 0.42 : 1.25} color={colors.key} />
      <pointLight
        position={[0.15, 3.05, 2.1]}
        intensity={USE_VRM_MODEL ? 7 : 28}
        color={colors.fill}
        distance={8}
      />
      <pointLight
        position={[-1.85, 2.2, 1.7]}
        intensity={USE_VRM_MODEL ? 4.8 : 18}
        color={colors.rim}
        distance={6.5}
      />
      <pointLight
        position={[1.9, 1.25, 1.35]}
        intensity={USE_VRM_MODEL ? 4.2 : 14}
        color={colors.key}
        distance={6.3}
      />
      <spotLight
        position={[0, 3.45, 1.7]}
        intensity={USE_VRM_MODEL ? 6.5 : 26}
        angle={0.44}
        penumbra={0.8}
        distance={10}
        color="#9ee8ff"
      />

      <mesh position={[0, 0, -3.2]}>
        <planeGeometry args={[8.4, 10]} />
        <meshBasicMaterial
          map={atmosphereTex}
          transparent
          opacity={USE_VRM_MODEL ? 0.74 : 0.98}
          depthWrite={false}
        />
      </mesh>

      <group ref={ringRef} position={[0, -0.12, -0.65]}>
        <mesh rotation={[Math.PI / 2.35, 0, 0]}>
          <torusGeometry args={[1.74, 0.028, 24, 96]} />
          <meshBasicMaterial
            color={colors.accent}
            transparent
            opacity={0.18}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
        <mesh rotation={[Math.PI / 1.95, 0, 0.44]}>
          <torusGeometry args={[1.1, 0.022, 20, 88]} />
          <meshBasicMaterial
            color={colors.rim}
            transparent
            opacity={0.12}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      </group>

      <mesh position={[0, 1.32, -0.35]} scale={[1.44, 1.88, 1]}>
        <planeGeometry args={[2.9, 3.8]} />
        <meshBasicMaterial
          ref={haloMatRef}
          map={haloTex}
          transparent
          opacity={USE_VRM_MODEL ? 0.24 : 0.55}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      <ModelBust expression={expression} deliveryStyle={deliveryStyle} playing={playing} />

      <EffectComposer>
        <Bloom
          luminanceThreshold={USE_VRM_MODEL ? 0.22 : 0.08}
          luminanceSmoothing={0.82}
          intensity={USE_VRM_MODEL ? 0.48 : 1.12}
          mipmapBlur
        />
        <ChromaticAberration
          offset={CA_OFFSET}
          radialModulation={false}
          modulationOffset={0}
        />
        <Noise opacity={0.035} blendFunction={BlendFunction.ADD} />
        <Vignette eskil={false} offset={0.12} darkness={0.72} />
      </EffectComposer>
    </>
  );
}

type Props = {
  expression: string;
  sync: AvatarSyncPayload | null;
  audioRef: React.RefObject<HTMLAudioElement | null>;
  playing: boolean;
};

export function AvatarRenderer({ expression, sync, playing }: Props) {
  const deliveryStyle = sync?.delivery_style ?? "normal";

  return (
    <div className={`avatar-hologram${playing ? " speaking" : ""}`}>
      <Canvas
        camera={{ fov: USE_VRM_MODEL ? 22.5 : 25.5, position: [0, 1.48, 2.88], near: 0.1, far: 100 }}
        gl={{ alpha: true, antialias: true }}
        dpr={[1, 2]}
      >
        <Suspense fallback={null}>
          <HologramScene
            expression={expression}
            deliveryStyle={deliveryStyle}
            playing={playing}
          />
        </Suspense>
      </Canvas>
    </div>
  );
}
