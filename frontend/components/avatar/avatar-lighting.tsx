"use client";

import { useEffect } from "react";
import * as THREE from "three";
import { useFrame, useThree } from "@react-three/fiber";
import {
  Bloom,
  ChromaticAberration,
  EffectComposer,
  Noise,
  Vignette,
} from "@react-three/postprocessing";
import { BlendFunction } from "postprocessing";

import { CA_OFFSET, type AvatarAssetKind, isVrmAsset, VISIBLE_LOOK_AT } from "./avatar-constants";

type AvatarLightingProps = {
  colors: { key: string; fill: string; rim: string; accent: string };
  assetKind: AvatarAssetKind;
};

export function CameraRig({ assetKind }: { assetKind: AvatarAssetKind }) {
  const { camera, gl } = useThree();
  const isVrm = isVrmAsset(assetKind);

  useEffect(() => {
    gl.toneMapping = THREE.ACESFilmicToneMapping;
    gl.toneMappingExposure = isVrm ? 0.64 : 0.82;
    camera.lookAt(VISIBLE_LOOK_AT);
    camera.updateProjectionMatrix();
  }, [camera, gl, isVrm]);

  useFrame(() => {
    camera.lookAt(VISIBLE_LOOK_AT);
  });

  return null;
}

export function AvatarLighting({ colors, assetKind }: AvatarLightingProps) {
  const isVrm = isVrmAsset(assetKind);

  return (
    <>
      <ambientLight intensity={isVrm ? 0.48 : 1.25} color={colors.key} />
      <pointLight
        position={[0.15, 3.05, 2.1]}
        intensity={isVrm ? 6.2 : 28}
        color={colors.fill}
        distance={8}
      />
      <pointLight
        position={[-1.85, 2.2, 1.7]}
        intensity={isVrm ? 5.6 : 18}
        color={colors.rim}
        distance={6.5}
      />
      <pointLight
        position={[1.9, 1.25, 1.35]}
        intensity={isVrm ? 3.7 : 14}
        color={colors.key}
        distance={6.3}
      />
      <spotLight
        position={[0, 3.45, 1.7]}
        intensity={isVrm ? 5.6 : 26}
        angle={0.44}
        penumbra={0.8}
        distance={10}
        color="#9ee8ff"
      />
    </>
  );
}

export function AvatarPostEffects({ assetKind }: { assetKind: AvatarAssetKind }) {
  const isVrm = isVrmAsset(assetKind);

  return (
    <EffectComposer>
      <Bloom
        luminanceThreshold={isVrm ? 0.28 : 0.08}
        luminanceSmoothing={0.84}
        intensity={isVrm ? 0.34 : 1.12}
        mipmapBlur
      />
      <ChromaticAberration
        offset={CA_OFFSET}
        radialModulation={false}
        modulationOffset={0}
      />
      <Noise opacity={0.028} blendFunction={BlendFunction.ADD} />
      <Vignette eskil={false} offset={0.12} darkness={0.68} />
    </EffectComposer>
  );
}
