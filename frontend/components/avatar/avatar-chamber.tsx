"use client";

import { useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";

import { EXPRESSION_TINT, isVrmAsset } from "./avatar-constants";
import type { AvatarSceneProps } from "./avatar-types";
import { ModelBust } from "./avatar-loader";
import { AvatarLighting, AvatarPostEffects, CameraRig } from "./avatar-lighting";

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
  gradient.addColorStop(0.55, "rgba(126, 242, 255, 0.07)");
  gradient.addColorStop(1, "rgba(255, 123, 136, 0.18)");
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
  background.addColorStop(0.45, "rgba(10,18,32,0.22)");
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
  crownGlow.addColorStop(0, "rgba(126,242,255,0.22)");
  crownGlow.addColorStop(0.54, "rgba(126,242,255,0.08)");
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
  lowerFog.addColorStop(0, "rgba(255,123,136,0.1)");
  lowerFog.addColorStop(0.62, "rgba(126,242,255,0.07)");
  lowerFog.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = lowerFog;
  ctx.fillRect(0, 0, width, height);

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

export function HologramScene({
  expression,
  deliveryStyle,
  playing,
  sync,
  audioRef,
  assetKind,
}: AvatarSceneProps) {
  const ringRef = useRef<THREE.Group>(null);
  const haloMatRef = useRef<THREE.MeshBasicMaterial>(null);
  const atmosphereTex = useMemo(() => buildAtmosphereTexture(), []);
  const haloTex = useMemo(() => buildHaloTexture(), []);
  const colors = EXPRESSION_TINT[expression] ?? EXPRESSION_TINT.neutral;
  const isVrm = isVrmAsset(assetKind);

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
        playing ? 0.62 : 0.42,
        1 - Math.exp(-4 * delta),
      );
      haloMatRef.current.color.set(colors.accent);
    }
  });

  return (
    <>
      <CameraRig assetKind={assetKind} />
      <AvatarLighting colors={colors} assetKind={assetKind} />

      <mesh position={[0, 0, -3.2]}>
        <planeGeometry args={[8.4, 10]} />
        <meshBasicMaterial
          map={atmosphereTex}
          transparent
          opacity={isVrm ? 0.62 : 0.98}
          depthWrite={false}
        />
      </mesh>

      <group ref={ringRef} position={[0, -0.12, -0.65]}>
        <mesh rotation={[Math.PI / 2.35, 0, 0]}>
          <torusGeometry args={[1.74, 0.028, 24, 96]} />
          <meshBasicMaterial
            color={colors.accent}
            transparent
            opacity={0.14}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
        <mesh rotation={[Math.PI / 1.95, 0, 0.44]}>
          <torusGeometry args={[1.1, 0.022, 20, 88]} />
          <meshBasicMaterial
            color={colors.rim}
            transparent
            opacity={0.1}
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
          opacity={isVrm ? 0.2 : 0.55}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>

      <ModelBust
        expression={expression}
        deliveryStyle={deliveryStyle}
        playing={playing}
        sync={sync}
        audioRef={audioRef}
        assetKind={assetKind}
      />

      <AvatarPostEffects assetKind={assetKind} />
    </>
  );
}
