import type { RefObject } from "react";

import type { AvatarSyncPayload, LifeStateName, PerceptionState } from "@/lib/types";
import type { AvatarAssetKind } from "./avatar-constants";

export type AvatarModelProps = {
  expression: string;
  deliveryStyle: string;
  playing: boolean;
  sync: AvatarSyncPayload | null;
  audioRef: RefObject<HTMLAudioElement | null>;
  assetKind: AvatarAssetKind;
  compact?: boolean;
  lifeState?: LifeStateName;
  perceptionState?: PerceptionState | null;
};

export type AvatarSceneProps = AvatarModelProps;

export type AvatarRendererProps = {
  expression: string;
  sync: AvatarSyncPayload | null;
  audioRef: RefObject<HTMLAudioElement | null>;
  playing: boolean;
  compact?: boolean;
  lifeState?: LifeStateName;
  perceptionState?: PerceptionState | null;
};

export type AvatarLoadState = "loading" | "ready" | "fallback" | "error";
