"use client";

import { Component, Suspense, useCallback, useState, type ErrorInfo, type ReactNode } from "react";
import { Canvas } from "@react-three/fiber";

import {
  ACTIVE_AVATAR_ASSET,
  GLB_CAMERA_FOV,
  GLB_CAMERA_POSITION,
  type AvatarAssetKind,
  isVrmAsset,
  VRM_CAMERA_FOV,
  VRM_CAMERA_POSITION,
} from "@/components/avatar/avatar-constants";
import { HologramScene } from "@/components/avatar/avatar-chamber";
import type { AvatarRendererProps } from "@/components/avatar/avatar-types";

function AvatarLoadingFallback() {
  return (
    <group>
      <mesh position={[0, 1.18, -0.2]}>
        <sphereGeometry args={[0.18, 24, 16]} />
        <meshBasicMaterial color="#7ef2ff" transparent opacity={0.18} />
      </mesh>
    </group>
  );
}

type AvatarErrorBoundaryProps = {
  children: ReactNode;
  onRenderError: (error: Error) => void;
};

type AvatarErrorBoundaryState = {
  failed: boolean;
};

class AvatarErrorBoundary extends Component<AvatarErrorBoundaryProps, AvatarErrorBoundaryState> {
  state: AvatarErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): AvatarErrorBoundaryState {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[Joi avatar] render failed", error, info);
    this.props.onRenderError(error);
  }

  render() {
    if (this.state.failed) {
      return <AvatarLoadingFallback />;
    }

    return this.props.children;
  }
}

export function AvatarRenderer({ expression, sync, audioRef, playing }: AvatarRendererProps) {
  const deliveryStyle = sync?.delivery_style ?? "normal";
  const [assetKind, setAssetKind] = useState<AvatarAssetKind>(ACTIVE_AVATAR_ASSET);
  const [renderError, setRenderError] = useState<Error | null>(null);
  const isVrm = isVrmAsset(assetKind);
  const cameraPosition = isVrm ? VRM_CAMERA_POSITION : GLB_CAMERA_POSITION;

  const handleRenderError = useCallback(
    (error: Error) => {
      if (assetKind === "vrm") {
        setAssetKind("glb");
        setRenderError(null);
        return;
      }

      setRenderError(error);
    },
    [assetKind],
  );

  if (renderError) {
    return (
      <div className="avatar-hologram avatar-hologram-error">
        <div className="avatar-renderer-status">
          <strong>Avatar renderer unavailable</strong>
          <span>{renderError.message}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`avatar-hologram${playing ? " speaking" : ""}`}>
      <Canvas
        camera={{
          fov: isVrm ? VRM_CAMERA_FOV : GLB_CAMERA_FOV,
          position: [cameraPosition.x, cameraPosition.y, cameraPosition.z],
          near: 0.1,
          far: 100,
        }}
        gl={{ alpha: true, antialias: true }}
        dpr={[1, 2]}
      >
        <AvatarErrorBoundary key={assetKind} onRenderError={handleRenderError}>
          <Suspense fallback={<AvatarLoadingFallback />}>
            <HologramScene
              expression={expression}
              deliveryStyle={deliveryStyle}
              playing={playing}
              sync={sync}
              audioRef={audioRef}
              assetKind={assetKind}
            />
          </Suspense>
        </AvatarErrorBoundary>
      </Canvas>
      {assetKind === "glb" && ACTIVE_AVATAR_ASSET === "vrm" ? (
        <div className="avatar-renderer-status avatar-renderer-status-compact">
          <span>GLB fallback</span>
        </div>
      ) : null}
    </div>
  );
}
