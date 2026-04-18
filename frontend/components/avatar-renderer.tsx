"use client";

import { Suspense, useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { Canvas, useFrame, useLoader, useThree } from "@react-three/fiber";
import {
  Bloom,
  ChromaticAberration,
  EffectComposer,
  Noise,
  Vignette,
} from "@react-three/postprocessing";
import { BlendFunction } from "postprocessing";

import { AvatarSyncPayload } from "@/lib/types";

// ── Texture URL tables ────────────────────────────────────────────────────

const FACE_URLS = [
  "/avatar/Joi_Neutral.png",   // 0
  "/avatar/Joi_Smile.png",     // 1
  "/avatar/Joi_Frown.png",     // 2
  "/avatar/Joi_Shock.png",     // 3
  "/avatar/Joi_Smirk.png",     // 4
];

const FACE_IDX: Record<string, number> = {
  neutral: 0, positive: 1, smile: 1, satisfied: 1,
  stress: 2, concern: 2, negative: 2, needy: 2, clingy: 2,
  shock: 3, missing: 4, smirk: 4,
};

const MOUTH_URLS = [
  "/avatar/mouth_overlays/mouth_ah.png",    // 0 → A / AI
  "/avatar/mouth_overlays/mouth_ee.png",    // 1 → E
  "/avatar/mouth_overlays/mouth_O.png",     // 2 → O
  "/avatar/mouth_overlays/mouth_W.png",     // 3 → U / W
  "/avatar/mouth_overlays/mouth_M.png",     // 4 → MB
  "/avatar/mouth_overlays/mouth_F.png",     // 5 → FV
  "/avatar/mouth_overlays/mouth_B.png",     // 6 → B
  "/avatar/mouth_overlays/mouth_K.png",     // 7 → K
  "/avatar/mouth_overlays/mouth_L.png",     // 8 → L
  "/avatar/mouth_overlays/mouth_R.png",     // 9 → R
  "/avatar/mouth_overlays/mouth_S.png",     // 10 → S
  "/avatar/mouth_overlays/mouth_TH.png",    // 11 → TH
  "/avatar/mouth_overlays/mouth_Oh.png",    // 12 → Oh
  "/avatar/mouth_overlays/mouth_rest.png",  // 13 → rest (fallback)
];

const PHONEME_MOUTH_IDX: Record<string, number | null> = {
  rest: null,
  A: 0, AI: 0,
  E: 1,
  O: 2,
  U: 3, W: 3,
  MB: 4, FV: 5, B: 6, K: 7, L: 8, R: 9, S: 10, TH: 11, Oh: 12,
};

// Mouth openness 0-3 scale — used to detect wide-jump transitions
const OPENNESS: Record<string, number> = {
  rest: 1, MB: 0, FV: 0, B: 0,
  S: 1, K: 1, TH: 1, L: 1, R: 1,
  E: 2, U: 2, W: 2,
  A: 3, O: 3, Oh: 3,
};

const VOWELS = new Set(["A", "E", "O", "U", "Oh", "AI"]);

// Returns lerp decay speed matching the CSS fade durations from Sprint 4.1.
// Formula: speed = -ln(0.01) / targetSeconds ≈ 4.605 / targetSeconds
function mouthFadeSpeed(phoneme: string, prev: string): number {
  const jump = Math.abs((OPENNESS[phoneme] ?? 1) - (OPENNESS[prev] ?? 1));
  if (jump >= 2) return 18;   // ~0.25 s blend for wide jumps (A → MB)
  return VOWELS.has(phoneme) ? 23 : 58;  // ~0.20 s vowel, ~0.08 s consonant
}

// ── Procedural edge-glow halo texture ────────────────────────────────────

function buildHaloTexture(): THREE.CanvasTexture {
  const sz = 512;
  const el = document.createElement("canvas");
  el.width = sz;
  el.height = sz;
  const ctx = el.getContext("2d")!;
  // Transparent center, cyan/violet glow at rim
  const g = ctx.createRadialGradient(sz / 2, sz / 2, sz * 0.3, sz / 2, sz / 2, sz * 0.5);
  g.addColorStop(0,    "rgba(80, 200, 255, 0)");
  g.addColorStop(0.65, "rgba(80, 200, 255, 0.07)");
  g.addColorStop(1,    "rgba(140, 160, 255, 0.32)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, sz, sz);
  return new THREE.CanvasTexture(el);
}

// ── Static CA offset (avoids new Vector2 on every render) ─────────────────

const CA_OFFSET = new THREE.Vector2(0.0022, 0.0022);

// ── Inner R3F scene component ─────────────────────────────────────────────

// Per-style motion amplitude multiplier for head animations
const MOTION_SCALE: Record<string, number> = {
  whisper:  0.50,  // calm, minimal movement
  intense:  1.40,  // emphatic, larger motions
  hesitant: 0.70,  // uncertain, restrained
  stressed: 0.80,  // tight, controlled
  normal:   1.00,
};

// Wide-mouth phonemes that trigger a stressed-vowel head nod
const WIDE_PHONEMES = new Set(["A", "O", "Oh", "AI"]);

type SceneProps = {
  expression: string;
  deliveryStyle: string;
  sync: AvatarSyncPayload | null;
  audioRef: React.RefObject<HTMLAudioElement | null>;
};

const ALL_URLS = [...FACE_URLS, ...MOUTH_URLS];

function HologramScene({ expression, deliveryStyle, sync, audioRef }: SceneProps) {
  const { viewport } = useThree();

  // Suspend until all textures are loaded
  const textures = useLoader(THREE.TextureLoader, ALL_URLS) as THREE.Texture[];
  const faceTextures  = textures.slice(0, FACE_URLS.length);
  const mouthTextures = textures.slice(FACE_URLS.length);

  // Procedural halo (canvas API, client-only, cheap to build once)
  const haloTex = useMemo(() => buildHaloTexture(), []);

  // Three.js object refs — updated imperatively in useFrame to avoid re-renders
  const rigRef      = useRef<THREE.Group>(null);
  const faceMatRef  = useRef<THREE.MeshBasicMaterial>(null);
  const mouthARef   = useRef<THREE.MeshBasicMaterial>(null);
  const mouthBRef   = useRef<THREE.MeshBasicMaterial>(null);

  // Lip-sync playback state (all refs, never setState inside useFrame)
  const activeMouthRef      = useRef<"a" | "b">("a");
  const lastPhonemeRef      = useRef("rest");
  const mouthATargetRef     = useRef(0);
  const mouthBTargetRef     = useRef(0);
  const fadeSpeedRef        = useRef(58);
  const syncRef             = useRef(sync);
  const deliveryStyleRef    = useRef(deliveryStyle);
  // Stressed-vowel head nod: set to a positive kick when a wide phoneme fires,
  // then decays to zero each frame
  const stressNodRef        = useRef(0);

  useEffect(() => { syncRef.current = sync; }, [sync]);
  useEffect(() => { deliveryStyleRef.current = deliveryStyle; }, [deliveryStyle]);

  // Reset mouth state whenever new audio arrives
  useEffect(() => {
    activeMouthRef.current  = "a";
    lastPhonemeRef.current  = "rest";
    mouthATargetRef.current = 0;
    mouthBTargetRef.current = 0;
  }, [sync?.audio_url]);

  // Swap face texture when expression/sentiment changes
  useEffect(() => {
    if (!faceMatRef.current) return;
    faceMatRef.current.map = faceTextures[FACE_IDX[expression] ?? 0];
    faceMatRef.current.needsUpdate = true;
  }, [expression, faceTextures]);

  // Idle blink — random 3-6 s, 130 ms snap, skipped while speaking
  useEffect(() => {
    let t: ReturnType<typeof setTimeout>;
    function scheduleBlink() {
      t = setTimeout(() => {
        const audio = audioRef.current;
        if (faceMatRef.current && (!audio || audio.paused || audio.ended)) {
          faceMatRef.current.opacity = 0.3;
          setTimeout(() => {
            if (faceMatRef.current) faceMatRef.current.opacity = 1.0;
          }, 130);
        }
        scheduleBlink();
      }, 3000 + Math.random() * 3000);
    }
    scheduleBlink();
    return () => clearTimeout(t);
  }, [audioRef]);

  useFrame((state, delta) => {
    const et  = state.clock.elapsedTime;
    const ms  = MOTION_SCALE[deliveryStyleRef.current] ?? 1.0;

    // ── Idle head motion (amplitude scaled by delivery style) ─────────────
    if (rigRef.current) {
      // Decay the stressed-vowel nod from previous frame
      stressNodRef.current *= Math.max(0, 1 - 9 * delta);

      // Breathing Y float + vowel-nod kick
      const baseY = Math.sin(et * 0.78) * 0.007 * viewport.height * ms;
      rigRef.current.position.y = baseY + stressNodRef.current;

      // Slow weight-shift Z tilt
      rigRef.current.rotation.z = Math.sin(et * 0.34) * 0.011 * ms;
      // Gaze drift left-right
      rigRef.current.rotation.y = Math.sin(et * 0.21) * 0.017 * ms;
      // Gaze drift up-down
      rigRef.current.rotation.x = Math.sin(et * 0.17) * 0.008 * ms;
    }

    // ── Lip-sync ───────────────────────────────────────────────────────────
    const audio = audioRef.current;
    const s     = syncRef.current;

    if (audio && s && !audio.paused && !audio.ended) {
      let phoneme = "rest";
      for (const [time, label] of s.phoneme_timeline) {
        if (audio.currentTime >= (time as number)) phoneme = label as string;
        else break;
      }

      if (phoneme !== lastPhonemeRef.current) {
        const prev = lastPhonemeRef.current;
        lastPhonemeRef.current  = phoneme;
        fadeSpeedRef.current    = mouthFadeSpeed(phoneme, prev);

        // Stressed-vowel head nod: wide phonemes get a small upward kick
        if (WIDE_PHONEMES.has(phoneme)) {
          stressNodRef.current = 0.013 * viewport.height * ms;
        }

        const mouthIdx  = PHONEME_MOUTH_IDX[phoneme];
        const isA       = activeMouthRef.current === "a";
        const inMat     = isA ? mouthBRef.current : mouthARef.current;

        if (mouthIdx != null && inMat) {
          inMat.map = mouthTextures[mouthIdx];
          inMat.needsUpdate = true;
          mouthATargetRef.current = isA ? 0 : 1;
          mouthBTargetRef.current = isA ? 1 : 0;
        } else {
          mouthATargetRef.current = 0;
          mouthBTargetRef.current = 0;
        }
        activeMouthRef.current = isA ? "b" : "a";
      }
    } else if (!audio || audio.ended) {
      mouthATargetRef.current = 0;
      mouthBTargetRef.current = 0;
    }

    // Exponential-decay lerp for mouth opacity: reaches 99% in ~1/speed seconds
    const alpha = 1 - Math.exp(-fadeSpeedRef.current * delta);
    if (mouthARef.current) {
      mouthARef.current.opacity = THREE.MathUtils.lerp(
        mouthARef.current.opacity, mouthATargetRef.current, alpha,
      );
    }
    if (mouthBRef.current) {
      mouthBRef.current.opacity = THREE.MathUtils.lerp(
        mouthBRef.current.opacity, mouthBTargetRef.current, alpha,
      );
    }
  });

  // Viewport-filling plane dimensions
  const w = viewport.width;
  const h = viewport.height;
  const initFaceTex = faceTextures[FACE_IDX[expression] ?? 0];

  return (
    <>
      <group ref={rigRef}>
        {/* ── Expression face layer (z=0) ── */}
        <mesh position={[0, 0, 0]}>
          <planeGeometry args={[w, h]} />
          <meshBasicMaterial ref={faceMatRef} map={initFaceTex} transparent />
        </mesh>

        {/* ── Mouth overlay A (z=0.02) ── */}
        <mesh position={[0, 0, 0.02]}>
          <planeGeometry args={[w, h]} />
          <meshBasicMaterial
            ref={mouthARef}
            map={mouthTextures[13]}
            transparent
            opacity={0}
          />
        </mesh>

        {/* ── Mouth overlay B (z=0.04) ── */}
        <mesh position={[0, 0, 0.04]}>
          <planeGeometry args={[w, h]} />
          <meshBasicMaterial
            ref={mouthBRef}
            map={mouthTextures[13]}
            transparent
            opacity={0}
          />
        </mesh>

        {/* ── Additive cyan rim halo (z=0.06) ── */}
        <mesh position={[0, 0, 0.06]}>
          <planeGeometry args={[w * 1.06, h * 1.06]} />
          <meshBasicMaterial
            map={haloTex}
            transparent
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      </group>

      {/* ── Postprocessing ─────────────────────────────────────────────── */}
      <EffectComposer>
        {/* Bloom: bright edges and face highlights glow cyan/violet */}
        <Bloom
          luminanceThreshold={0.1}
          luminanceSmoothing={0.85}
          intensity={0.9}
          mipmapBlur
        />
        {/* Chromatic aberration: RGB fringe at edges */}
        <ChromaticAberration
          offset={CA_OFFSET}
          radialModulation={false}
          modulationOffset={0}
        />
        {/* Film grain: subtle holographic noise texture */}
        <Noise opacity={0.04} blendFunction={BlendFunction.ADD} />
        {/* Vignette: darken corners for cinematic depth */}
        <Vignette eskil={false} offset={0.12} darkness={0.65} />
      </EffectComposer>
    </>
  );
}

// ── Public component ──────────────────────────────────────────────────────

type Props = {
  expression: string;
  sync: AvatarSyncPayload | null;
  audioRef: React.RefObject<HTMLAudioElement | null>;
  playing: boolean;
};

export function AvatarRenderer({ expression, sync, audioRef, playing }: Props) {
  const deliveryStyle = sync?.delivery_style ?? "normal";

  return (
    <div className={`avatar-hologram${playing ? " speaking" : ""}`}>
      <Canvas
        orthographic
        camera={{ zoom: 100, position: [0, 0, 10], near: 0.1, far: 100 }}
        gl={{ alpha: true, antialias: false }}
        dpr={[1, 2]}
      >
        <Suspense fallback={null}>
          <HologramScene
            expression={expression}
            deliveryStyle={deliveryStyle}
            sync={sync}
            audioRef={audioRef}
          />
        </Suspense>
      </Canvas>
    </div>
  );
}
