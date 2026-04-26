"use client";

import { useEffect, useLayoutEffect, useRef } from "react";
import * as THREE from "three";
import { useFrame, useLoader } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRM, VRMLoaderPlugin } from "@pixiv/three-vrm";

import {
  GLB_BUST_GROUP_OFFSET,
  GLB_MODEL_URL,
  GLB_TARGET_HEIGHT,
  GLB_VERTICAL_OFFSET,
  GLB_Y_ROTATION,
  LIFE_STATE_IDLE_MOTION_SCALE,
  MOTION_SCALE,
  VRM_FLOOR_OFFSET,
  VRM_MODEL_URL,
  VRM_TARGET_HEIGHT,
} from "./avatar-constants";
import type { AvatarModelProps } from "./avatar-types";
import { auditVrm } from "./avatar-audit";
import {
  applyExpressionWeights,
  getExpressionTargets,
  type ExpressionWeights,
  smoothWeights,
} from "./avatar-expression";
import { createIdlePoseState, updateVrmIdlePose } from "./avatar-pose";
import { getSpeechTargets, smoothSpeechWeights, VRM_VISEME_NAMES } from "./avatar-speech";

useGLTF.preload(GLB_MODEL_URL);

function tuneMaterial(material: THREE.Material): void {
  material.needsUpdate = true;

  if ("toneMapped" in material) {
    (material as THREE.Material & { toneMapped: boolean }).toneMapped = true;
  }

  if (material instanceof THREE.MeshStandardMaterial) {
    material.roughness = Math.max(material.roughness, 0.58);
    material.metalness = Math.min(material.metalness, 0.05);
    material.envMapIntensity = 0.34;
  }

  if (material instanceof THREE.MeshPhysicalMaterial) {
    material.roughness = Math.max(material.roughness, 0.56);
    material.metalness = Math.min(material.metalness, 0.04);
    material.envMapIntensity = 0.36;
  }
}

function prepareModelMaterials(model: THREE.Object3D, doubleSide = false): void {
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
      if (doubleSide) {
        material.side = THREE.DoubleSide;
      }
      tuneMaterial(material);
    }
  });
}

function useVrm(url: string): VRM | null {
  const gltf = useLoader(GLTFLoader, url, (loader) => {
    loader.register((parser) => new VRMLoaderPlugin(parser));
  });

  return (gltf.userData.vrm as VRM | undefined) ?? null;
}

function VrmBust({ expression, deliveryStyle, playing, sync, audioRef, lifeState }: AvatarModelProps) {
  const vrm = useVrm(VRM_MODEL_URL);
  const rigRef = useRef<THREE.Group>(null);
  const loggedRef = useRef(false);
  const idleRef = useRef(createIdlePoseState());
  const expressionWeightsRef = useRef<ExpressionWeights>({});
  const speechWeightsRef = useRef<ExpressionWeights>({});

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
    model.position.set(0, 0, 0);
    model.scale.setScalar(1);
    model.rotation.set(0, 0, 0);
    model.updateMatrixWorld(true);

    const bounds = new THREE.Box3().setFromObject(model);
    const size = bounds.getSize(new THREE.Vector3());
    const center = bounds.getCenter(new THREE.Vector3());
    const scale = VRM_TARGET_HEIGHT / Math.max(size.y, 0.001);

    model.scale.setScalar(scale);
    model.position.set(-center.x * scale, -bounds.min.y * scale + VRM_FLOOR_OFFSET, -center.z * scale);
    model.rotation.set(0, 0, 0);
    model.updateMatrixWorld(true);
    prepareModelMaterials(model);
  }, [vrm]);

  useFrame((state, delta) => {
    if (!vrm || !rigRef.current) {
      return;
    }

    const elapsed = state.clock.elapsedTime;
    const baseMotionScale = MOTION_SCALE[deliveryStyle] ?? 1;
    // During idle (not speaking), multiply by the life-state scale so resting/calm
    // states feel quieter without killing motion entirely. While playing, use the
    // delivery-style scale unmodified to keep speech animation natural.
    const lifeMultiplier = playing ? 1 : (LIFE_STATE_IDLE_MOTION_SCALE[lifeState ?? "calm"] ?? 1);
    const motionScale = baseMotionScale * lifeMultiplier;
    const expressionManager = vrm.expressionManager;

    expressionManager?.resetValues();
    updateVrmIdlePose(vrm, rigRef.current, idleRef.current, elapsed, delta, {
      expression,
      motionScale,
      playing,
    });

    expressionWeightsRef.current = smoothWeights(
      expressionWeightsRef.current,
      getExpressionTargets(expression, playing),
      delta,
      6.8,
    );
    speechWeightsRef.current = smoothSpeechWeights(
      speechWeightsRef.current,
      getSpeechTargets(sync, audioRef, playing),
      delta,
    );

    applyExpressionWeights(vrm, expressionWeightsRef.current);
    applyExpressionWeights(vrm, speechWeightsRef.current);
    for (const name of VRM_VISEME_NAMES) {
      if (!(name in speechWeightsRef.current)) {
        applyExpressionWeights(vrm, { [name]: 0 });
      }
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

function StaticGlbBust({ deliveryStyle, playing, lifeState }: AvatarModelProps) {
  const { scene } = useGLTF(GLB_MODEL_URL);
  const model = scene;
  const rigRef = useRef<THREE.Group>(null);

  useLayoutEffect(() => {
    model.position.set(0, 0, 0);
    model.scale.setScalar(1);
    model.rotation.set(0, 0, 0);
    model.updateMatrixWorld(true);

    const bounds = new THREE.Box3().setFromObject(model);
    const size = bounds.getSize(new THREE.Vector3());
    const center = bounds.getCenter(new THREE.Vector3());
    const scale = GLB_TARGET_HEIGHT / Math.max(size.y, 0.001);

    model.position.set(-center.x, -center.y + GLB_VERTICAL_OFFSET, -center.z);
    model.scale.setScalar(scale);
    model.updateMatrixWorld(true);
    prepareModelMaterials(model, true);
  }, [model]);

  useFrame((state) => {
    if (!rigRef.current) {
      return;
    }

    const elapsed = state.clock.elapsedTime;
    const baseMotionScale = MOTION_SCALE[deliveryStyle] ?? 1;
    const lifeMultiplier = playing ? 1 : (LIFE_STATE_IDLE_MOTION_SCALE[lifeState ?? "calm"] ?? 1);
    const motionScale = baseMotionScale * lifeMultiplier;
    const speakingBoost = playing ? 1.24 : 1;
    const breathing = Math.sin(elapsed * 0.86) * 0.038 * motionScale;
    const settle = Math.sin(elapsed * 0.26) * 0.024 * motionScale;

    rigRef.current.position.y = GLB_BUST_GROUP_OFFSET.y - 0.22 + breathing;
    rigRef.current.position.x =
      GLB_BUST_GROUP_OFFSET.x + Math.sin(elapsed * 0.21) * 0.045 * motionScale;
    rigRef.current.position.z = GLB_BUST_GROUP_OFFSET.z;
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

export function ModelBust(props: AvatarModelProps) {
  if (props.assetKind === "vrm") {
    return <VrmBust {...props} />;
  }

  return <StaticGlbBust {...props} />;
}
