"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { analyzeSnapshot, fetchPerceptionPolicy } from "@/lib/api";
import type { PerceptionPolicy, PerceptionSignal, PerceptionSignalType, SnapshotAnalysis } from "@/lib/types";

// MediaPipe runs entirely in the local browser context via WebAssembly.
// WASM is served from the installed package. The face model is vendored
// under public/ and is required for camera perception to start.
const LOCAL_MEDIAPIPE_WASM_URL = "/vendor/mediapipe/tasks-vision/wasm";
const LOCAL_FACE_LANDMARKER_MODEL_URL = "/vendor/mediapipe/models/face_landmarker.task";
const REMOTE_MEDIAPIPE_WASM_URL = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.34/wasm";

const POLL_INTERVAL_MS = 250; // 4fps - enough for presence, low CPU cost
const LOOK_AWAY_THRESHOLD_MS = 2000; // emit looked_away after 2s of no face
const PRESENCE_STABILITY_FRAMES = 2;
const LEAN_STABILITY_FRAMES = 2;
const LEAN_IN_THRESHOLD = 0.38; // face width as fraction of frame width
const LEAN_OUT_THRESHOLD = 0.30;
const EXPRESSION_DEBOUNCE_MS = 600; // min ms between expression change signals
const EXPRESSION_STABILITY_FRAMES = 3;
const EXPRESSION_MIN_CONFIDENCE = 0.35;
const POLICY_POLL_INTERVAL_MS = 3000;

// ARKit blendshape thresholds for expression classification
const SMILE_THRESHOLD    = 0.45;
const BROW_DOWN_THRESHOLD = 0.35;
const FROWN_THRESHOLD    = 0.40;
const EYE_WIDE_THRESHOLD = 0.40;
const JAW_OPEN_THRESHOLD = 0.30;

// MediaPipe/TFLite route their native glog INFO/WARNING lines (e.g. "Created
// TensorFlow Lite XNNPACK delegate for CPU") through console.error, which the
// Next.js dev overlay then surfaces as a scary "Console Error". These are
// informational, not failures — filter just those benign lines once so the
// overlay stops crying wolf. Real errors (which never carry these prefixes)
// pass through untouched.
let mediapipeLogsFiltered = false;
function filterBenignMediapipeLogs(): void {
  if (mediapipeLogsFiltered || typeof window === "undefined") return;
  mediapipeLogsFiltered = true;
  const benign = /^(INFO|WARNING): |Created TensorFlow Lite|XNNPACK delegate/;
  for (const method of ["error", "info"] as const) {
    const original = console[method].bind(console);
    console[method] = (...args: unknown[]) => {
      if (typeof args[0] === "string" && benign.test(args[0])) return;
      original(...args);
    };
  }
}

type ExpressionLabel = "smile" | "possible_tension" | "surprise" | "neutral";

type ExpressionCandidate = {
  label: ExpressionLabel;
  confidence: number;
};

type EngineStatus = "idle" | "requesting" | "loading" | "active" | "error" | "denied";

type SnapshotStatus = "idle" | "capturing" | "analyzing" | "done" | "error";

type AssetMode = "local" | "remote-fallback" | "missing" | "unknown";

type PerceptionEngineProps = {
  sessionId: string | null;
  onSignal: (signal: PerceptionSignal) => void;
  onActiveChange?: (active: boolean) => void;
};

function emit(signal: PerceptionSignalType, confidence?: number): PerceptionSignal {
  return { signal, timestamp: performance.now(), confidence };
}

function setNativeCameraActive(active: boolean): void {
  const nativeApi = (
    window as Window & {
      pywebview?: {
        api?: {
          set_camera_active?: (active: boolean) => Promise<boolean> | boolean;
        };
      };
    }
  ).pywebview?.api;

  void Promise.resolve(nativeApi?.set_camera_active?.(active)).catch(() => null);
}

async function urlExists(url: string): Promise<boolean> {
  try {
    const response = await fetch(url, { method: "HEAD", cache: "no-store" });
    return response.ok;
  } catch {
    return false;
  }
}

export function PerceptionEngine({ sessionId, onSignal, onActiveChange }: PerceptionEngineProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const landmarkerRef = useRef<import("@mediapipe/tasks-vision").FaceLandmarker | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Presence state machine
  const lastFaceAtRef = useRef<number | null>(null);
  const faceWasPresentRef = useRef(false);
  const lookAwayFiredRef = useRef(false);
  const leanedInRef = useRef(false);
  const detectedFaceFramesRef = useRef(0);
  const missingFaceFramesRef = useRef(0);
  const pendingLeanStateRef = useRef<{ leanedIn: boolean; frames: number } | null>(null);

  // Expression state machine
  const lastExpressionRef = useRef<ExpressionLabel>("neutral");
  const lastExpressionEmittedAtRef = useRef<number>(0);
  const pendingExpressionRef = useRef<{ label: ExpressionLabel; confidence: number; frames: number } | null>(null);

  const [status, setStatus] = useState<EngineStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [facePresent, setFacePresent] = useState(false);
  const [snapshotStatus, setSnapshotStatus] = useState<SnapshotStatus>("idle");
  const [lastSnapshot, setLastSnapshot] = useState<SnapshotAnalysis | null>(null);
  const [policy, setPolicy] = useState<PerceptionPolicy | null>(null);
  const [wasmMode, setWasmMode] = useState<AssetMode>("unknown");
  const [modelMode, setModelMode] = useState<AssetMode>("unknown");

  useEffect(() => {
    let cancelled = false;

    const refreshPolicy = () => {
      fetchPerceptionPolicy()
        .then((r) => {
          if (!cancelled) setPolicy(r.policy);
        })
        .catch(() => null);
    };

    refreshPolicy();
    const policyTimer = window.setInterval(refreshPolicy, POLICY_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(policyTimer);
    };
  }, []);

  const stopEngine = useCallback(() => {
    if (pollTimerRef.current !== null) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    lastFaceAtRef.current = null;
    faceWasPresentRef.current = false;
    lookAwayFiredRef.current = false;
    leanedInRef.current = false;
    detectedFaceFramesRef.current = 0;
    missingFaceFramesRef.current = 0;
    pendingLeanStateRef.current = null;
    lastExpressionRef.current = "neutral";
    lastExpressionEmittedAtRef.current = 0;
    pendingExpressionRef.current = null;
    setFacePresent(false);
    setNativeCameraActive(false);
    setStatus("idle");
  }, []);

  useEffect(() => {
    return () => {
      if (pollTimerRef.current !== null) clearInterval(pollTimerRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      setNativeCameraActive(false);
    };
  }, []);

  useEffect(() => {
    if (policy?.camera_enabled === false && status !== "idle") {
      stopEngine();
    }
  }, [policy?.camera_enabled, status, stopEngine]);

  // Surface the true running state so consumers (chat) know the camera is on
  // even when a still, present user has stopped emitting change-signals.
  useEffect(() => {
    onActiveChange?.(status === "active");
  }, [status, onActiveChange]);

  function normFaceWidth(landmarks: { x: number; y: number }[]): number {
    let minX = 1, maxX = 0;
    for (const pt of landmarks) {
      if (pt.x < minX) minX = pt.x;
      if (pt.x > maxX) maxX = pt.x;
    }
    return maxX - minX;
  }

  function pickExpression(
    categories: Array<{ categoryName: string; score: number }>,
  ): ExpressionCandidate {
    const s = (name: string) =>
      categories.find((c) => c.categoryName === name)?.score ?? 0;

    const smile    = (s("mouthSmileLeft") + s("mouthSmileRight")) / 2;
    const browDown = (s("browDownLeft")   + s("browDownRight"))   / 2;
    const frown    = (s("mouthFrownLeft") + s("mouthFrownRight")) / 2;
    const eyeWide  = (s("eyeWideLeft")    + s("eyeWideRight"))    / 2;
    const jawOpen  = s("jawOpen");

    if (eyeWide > EYE_WIDE_THRESHOLD && jawOpen > JAW_OPEN_THRESHOLD) {
      return { label: "surprise", confidence: Math.min(1, (eyeWide + jawOpen) / 2) };
    }
    if (smile > SMILE_THRESHOLD) {
      return { label: "smile", confidence: smile };
    }
    if (browDown > BROW_DOWN_THRESHOLD || frown > FROWN_THRESHOLD) {
      return { label: "possible_tension", confidence: Math.max(browDown, frown) };
    }
    return { label: "neutral", confidence: 1 };
  }

  const runDetection = useCallback(() => {
    const video = videoRef.current;
    const landmarker = landmarkerRef.current;
    if (!video || !landmarker || video.readyState < 2) return;

    const now = performance.now();
    const result = landmarker.detectForVideo(video, now);
    const detected = result.faceLandmarks.length > 0;

    if (detected) {
      detectedFaceFramesRef.current += 1;
      missingFaceFramesRef.current = 0;
      lookAwayFiredRef.current = false;
      lastFaceAtRef.current = now;

      if (!faceWasPresentRef.current && detectedFaceFramesRef.current >= PRESENCE_STABILITY_FRAMES) {
        faceWasPresentRef.current = true;
        setFacePresent(true);
        onSignal(emit("returned_to_frame", 1));
        onSignal(emit("face_visible", 1));
        onSignal(emit("user_present", 1));
      }

      // Lean detection via normalized face bounding box width with frame-level stability.
      const landmarks = result.faceLandmarks[0];
      const faceWidth = normFaceWidth(landmarks);
      const nextLeanState =
        !leanedInRef.current && faceWidth > LEAN_IN_THRESHOLD
          ? true
          : leanedInRef.current && faceWidth < LEAN_OUT_THRESHOLD
            ? false
            : null;

      if (nextLeanState === null) {
        pendingLeanStateRef.current = null;
      } else {
        const pending = pendingLeanStateRef.current;
        pendingLeanStateRef.current =
          pending?.leanedIn === nextLeanState
            ? { leanedIn: nextLeanState, frames: pending.frames + 1 }
            : { leanedIn: nextLeanState, frames: 1 };

        if (pendingLeanStateRef.current.frames >= LEAN_STABILITY_FRAMES) {
          leanedInRef.current = nextLeanState;
          pendingLeanStateRef.current = null;
          onSignal(emit(nextLeanState ? "leaned_in" : "leaned_back", faceWidth));
        }
      }

      // Expression detection via ARKit blendshapes with neutral labels and frame stability.
      if (result.faceBlendshapes.length > 0) {
        const categories = result.faceBlendshapes[0].categories;
        const expression = pickExpression(categories);
        const pending = pendingExpressionRef.current;
        pendingExpressionRef.current =
          pending?.label === expression.label
            ? {
                label: expression.label,
                confidence: Math.max(pending.confidence, expression.confidence),
                frames: pending.frames + 1,
              }
            : { ...expression, frames: 1 };

        const timeSinceLast = now - lastExpressionEmittedAtRef.current;
        if (
          expression.label !== lastExpressionRef.current &&
          pendingExpressionRef.current.frames >= EXPRESSION_STABILITY_FRAMES &&
          pendingExpressionRef.current.confidence >= EXPRESSION_MIN_CONFIDENCE &&
          timeSinceLast >= EXPRESSION_DEBOUNCE_MS
        ) {
          lastExpressionRef.current = expression.label;
          lastExpressionEmittedAtRef.current = now;
          const signalType =
            expression.label === "smile"            ? "expression_smile"            :
            expression.label === "possible_tension" ? "expression_possible_tension" :
            expression.label === "surprise"         ? "expression_surprise"         :
                                                       "expression_neutral";
          onSignal(emit(signalType, pendingExpressionRef.current.confidence));
        }
      }
    } else {
      missingFaceFramesRef.current += 1;
      detectedFaceFramesRef.current = 0;
      pendingLeanStateRef.current = null;
      pendingExpressionRef.current = null;

      if (lastFaceAtRef.current !== null && !lookAwayFiredRef.current) {
        const elapsed = now - lastFaceAtRef.current;
        if (
          missingFaceFramesRef.current >= PRESENCE_STABILITY_FRAMES &&
          elapsed >= LOOK_AWAY_THRESHOLD_MS
        ) {
          lookAwayFiredRef.current = true;
          faceWasPresentRef.current = false;
          leanedInRef.current = false;
          setFacePresent(false);
          onSignal(emit("looked_away"));
        }
      }
    }
  }, [onSignal]);

  async function captureSnapshot() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || status !== "active" || !sessionId) return;

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.82);

    onSignal({ signal: "snapshot_captured", timestamp: performance.now() });
    setSnapshotStatus("analyzing");
    setLastSnapshot(null);

    try {
      const analysis = await analyzeSnapshot(sessionId, dataUrl);
      setLastSnapshot(analysis);
      setSnapshotStatus("done");
      onSignal({
        signal: "snapshot_analyzed",
        timestamp: performance.now(),
        payload: {
          description: analysis.description,
          tags: analysis.tags,
          capturedAt: analysis.capturedAt,
        },
      });
    } catch {
      setSnapshotStatus("error");
    }
  }

  async function startEngine() {
    if (policy?.camera_enabled === false) {
      setError("Camera access is suspended in Settings.");
      return;
    }

    setError(null);
    setStatus("requesting");

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: "user" },
      });
    } catch (cause) {
      const isDenied =
        cause instanceof Error &&
        (cause.name === "NotAllowedError" || cause.name === "PermissionDeniedError");
      setStatus(isDenied ? "denied" : "error");
      setError(isDenied ? "Camera access denied." : "Could not open camera.");
      return;
    }

    streamRef.current = stream;
    if (videoRef.current) {
      videoRef.current.srcObject = stream;
      await videoRef.current.play().catch(() => null);
    }

    setStatus("loading");

    try {
      filterBenignMediapipeLogs();
      const { FaceLandmarker, FilesetResolver } = await import("@mediapipe/tasks-vision");
      let vision: Awaited<ReturnType<typeof FilesetResolver.forVisionTasks>>;
      try {
        vision = await FilesetResolver.forVisionTasks(LOCAL_MEDIAPIPE_WASM_URL);
        setWasmMode("local");
      } catch {
        vision = await FilesetResolver.forVisionTasks(REMOTE_MEDIAPIPE_WASM_URL);
        setWasmMode("remote-fallback");
      }
      if (!(await urlExists(LOCAL_FACE_LANDMARKER_MODEL_URL))) {
        setModelMode("missing");
        throw new Error("Local face landmarker model is missing from the packaged frontend.");
      }
      setModelMode("local");
      landmarkerRef.current = await FaceLandmarker.createFromOptions(vision, {
        baseOptions: {
          modelAssetPath: LOCAL_FACE_LANDMARKER_MODEL_URL,
          delegate: "GPU",
        },
        numFaces: 1,
        runningMode: "VIDEO",
        outputFaceBlendshapes: true,
        outputFacialTransformationMatrixes: false,
      });
    } catch (cause) {
      setStatus("error");
      setError(cause instanceof Error ? cause.message : "Failed to load face detection model.");
      stream.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
      return;
    }

    // Reset state machines
    lastFaceAtRef.current = null;
    faceWasPresentRef.current = false;
    lookAwayFiredRef.current = false;
    leanedInRef.current = false;
    detectedFaceFramesRef.current = 0;
    missingFaceFramesRef.current = 0;
    pendingLeanStateRef.current = null;
    lastExpressionRef.current = "neutral";
    lastExpressionEmittedAtRef.current = 0;
    pendingExpressionRef.current = null;

    pollTimerRef.current = setInterval(runDetection, POLL_INTERVAL_MS);
    setNativeCameraActive(true);
    setStatus("active");
  }

  const STATUS_LABELS: Record<EngineStatus, string> = {
    idle: "off",
    requesting: "requesting camera",
    loading: "loading model",
    active: "sensing",
    error: "error",
    denied: "denied",
  };

  const badgeTone =
    status === "active"
      ? facePresent
        ? "ok"
        : "warn"
      : status === "error" || status === "denied"
        ? "warn"
        : "";

  return (
    <div className="panel">
      <p className="eyebrow">Perception</p>
      <h3>Presence sensing</h3>
      <p style={{ fontSize: "0.78rem", color: "var(--color-muted)", marginBottom: 10 }}>
        Face detection runs locally in your browser via WebAssembly. No video is sent to any server.
      </p>

      <div className="voice-badges" style={{ marginBottom: 12 }}>
        <span className={`badge ${badgeTone}`}>{STATUS_LABELS[status]}</span>
        {status === "active" ? (
          <span className={`badge ${facePresent ? "ok" : ""}`}>
            {facePresent ? "face detected" : "no face"}
          </span>
        ) : null}
        {status === "active" || status === "loading" ? (
          <>
            <span className={`badge ${wasmMode === "local" ? "ok" : "warn"}`}>
              WASM:{" "}
              {wasmMode === "local"
                ? "local"
                : wasmMode === "remote-fallback"
                  ? "remote fallback"
                  : "checking"}
            </span>
            <span className={`badge ${modelMode === "local" ? "ok" : "warn"}`}>
              Model:{" "}
              {modelMode === "local"
                ? "local"
                : modelMode === "missing"
                  ? "missing"
                  : "checking"}
            </span>
          </>
        ) : null}
      </div>

      {policy?.camera_enabled === false ? (
        <div className="empty-state" style={{ marginBottom: 12 }}>
          Camera access is disabled in{" "}
          <a href="/settings" style={{ color: "var(--color-accent)" }}>Settings - Perception Policy</a>.
        </div>
      ) : null}

      <div className="button-row">
        {status === "idle" || status === "error" || status === "denied" ? (
          <button
            className="button ghost"
            type="button"
            disabled={policy?.camera_enabled === false}
            onClick={() => void startEngine()}
          >
            Enable camera
          </button>
        ) : (
          <>
            <button
              className="button ghost"
              type="button"
              disabled={status === "requesting" || status === "loading"}
              onClick={stopEngine}
            >
              {status === "requesting" || status === "loading" ? "Starting..." : "Disable camera"}
            </button>
            <button
              className="button ghost"
              type="button"
              disabled={status !== "active" || !sessionId || snapshotStatus === "analyzing"}
              onClick={() => void captureSnapshot()}
            >
              {snapshotStatus === "analyzing" ? "Analyzing..." : "Capture scene"}
            </button>
          </>
        )}
      </div>

      {error ? <div className="voice-error" style={{ marginTop: 8 }}>{error}</div> : null}

      {lastSnapshot ? (
        <div style={{ marginTop: 12 }}>
          <img
            src={lastSnapshot.previewDataUrl}
            alt="Snapshot preview"
            style={{ width: "100%", borderRadius: 6, marginBottom: 8, opacity: 0.85 }}
          />
          <p style={{ fontSize: "0.78rem", color: "var(--color-muted)", margin: "4px 0 6px" }}>
            {lastSnapshot.description}
          </p>
          {lastSnapshot.tags.length > 0 ? (
            <div className="voice-badges">
              {lastSnapshot.tags.map((tag) => (
                <span className="badge" key={tag}>{tag}</span>
              ))}
            </div>
          ) : null}
          <button
            className="button ghost"
            type="button"
            style={{ marginTop: 8, fontSize: "0.72rem" }}
            onClick={() => { setLastSnapshot(null); setSnapshotStatus("idle"); }}
          >
            Clear
          </button>
        </div>
      ) : snapshotStatus === "error" ? (
        <div className="voice-error" style={{ marginTop: 8 }}>Scene analysis failed.</div>
      ) : null}

      {/* Hidden elements used only for frame capture — nothing leaves the browser until Capture is clicked */}
      <video
        ref={videoRef}
        playsInline
        muted
        style={{ position: "absolute", opacity: 0, pointerEvents: "none", width: 1, height: 1 }}
        aria-hidden
      />
      <canvas
        ref={canvasRef}
        style={{ position: "absolute", opacity: 0, pointerEvents: "none", width: 1, height: 1 }}
        aria-hidden
      />
    </div>
  );
}
