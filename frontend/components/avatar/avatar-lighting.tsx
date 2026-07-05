"use client";

import { useEffect } from "react";
import * as THREE from "three";
import { useFrame, useThree } from "@react-three/fiber";
import {
  Bloom,
  ChromaticAberration,
  EffectComposer,
  Glitch,
  Noise,
  Scanline,
  Vignette,
} from "@react-three/postprocessing";
import { BlendFunction, GlitchMode } from "postprocessing";

import {
  CA_OFFSET,
  getAvatarCameraConfig,
  type AvatarAssetKind,
  isVrmAsset,
} from "./avatar-constants";

type AvatarLightingProps = {
  colors: { key: string; fill: string; rim: string; accent: string };
  assetKind: AvatarAssetKind;
};

// Glitch effect expects Vector2 ranges; define once to avoid per-render allocs.
const GLITCH_DELAY = new THREE.Vector2(0, 0);
const GLITCH_DURATION = new THREE.Vector2(0.06, 0.16);
const GLITCH_STRENGTH = new THREE.Vector2(0.06, 0.22);

export function CameraRig({ assetKind, compact = false }: { assetKind: AvatarAssetKind; compact?: boolean }) {
  const { camera, gl } = useThree();
  const isVrm = isVrmAsset(assetKind);
  const { fov, lookAt, position } = getAvatarCameraConfig(assetKind, compact);

  useEffect(() => {
    gl.toneMapping = THREE.ACESFilmicToneMapping;
    gl.toneMappingExposure = isVrm ? 0.72 : 0.82;
    camera.position.copy(position);
    if (camera instanceof THREE.PerspectiveCamera) {
      camera.fov = fov;
    }
    camera.lookAt(lookAt);
    camera.updateProjectionMatrix();
  }, [camera, fov, gl, isVrm, lookAt, position]);

  useFrame(() => {
    camera.lookAt(lookAt);
  });

  return null;
}

export function AvatarLighting({ colors, assetKind }: AvatarLightingProps) {
  const isVrm = isVrmAsset(assetKind);

  return (
    <>
      <ambientLight intensity={isVrm ? 0.58 : 1.25} color={colors.key} />
      <pointLight
        position={[0.15, 3.05, 2.1]}
        intensity={isVrm ? 7.1 : 28}
        color={colors.fill}
        distance={8}
      />
      <pointLight
        position={[-1.85, 2.2, 1.7]}
        intensity={isVrm ? 5.2 : 18}
        color={colors.rim}
        distance={6.5}
      />
      <pointLight
        position={[1.9, 1.25, 1.35]}
        intensity={isVrm ? 3.9 : 14}
        color={colors.key}
        distance={6.3}
      />
      <spotLight
        position={[0, 3.45, 1.7]}
        intensity={isVrm ? 6.2 : 26}
        angle={0.44}
        penumbra={0.8}
        distance={10}
        color="#9ee8ff"
      />
    </>
  );
}

export function AvatarPostEffects({
  assetKind,
  glitchActive = false,
}: {
  assetKind: AvatarAssetKind;
  glitchActive?: boolean;
}) {
  const isVrm = isVrmAsset(assetKind);

  return (
    <EffectComposer>
      <Bloom
        luminanceThreshold={isVrm ? 0.28 : 0.08}
        luminanceSmoothing={0.84}
        intensity={isVrm ? 0.28 : 1.12}
        mipmapBlur
      />
      <ChromaticAberration
        offset={CA_OFFSET}
        radialModulation={false}
        modulationOffset={0}
      />
      {/* Faint projection scanlines — always on, low opacity so it reads as
          texture rather than a CRT filter. */}
      <Scanline blendFunction={BlendFunction.OVERLAY} density={1.15} opacity={0.045} />
      {/* Event-driven flicker: quiet by default, pulsed on for a beat when Joi
          materializes to speak or her state shifts (driven by HologramScene). */}
      <Glitch
        mode={glitchActive ? GlitchMode.CONSTANT_MILD : GlitchMode.DISABLED}
        active={glitchActive}
        delay={GLITCH_DELAY}
        duration={GLITCH_DURATION}
        strength={GLITCH_STRENGTH}
        ratio={0.72}
      />
      <Noise opacity={0.022} blendFunction={BlendFunction.ADD} />
      <Vignette eskil={false} offset={0.1} darkness={0.62} />
    </EffectComposer>
  );
}
