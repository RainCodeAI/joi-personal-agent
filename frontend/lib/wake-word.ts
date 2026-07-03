// Transcription-based wake-word detection. A heard utterance is transcribed
// locally, then checked here for the wake phrase. Matching is word-based so we
// can return the trailing command with its original casing/punctuation intact.

export const DEFAULT_WAKE_PHRASE = "hey joi";

// Whisper often renders "Joi" as "Joy", "Joey", "Choi", etc. Bare common words
// (e.g. "joy") are intentionally excluded to avoid false wakes; the "hey …"
// forms carry them safely. Users can override the primary phrase.
const BUILTIN_ALIASES = [
  "hey joi",
  "hey joy",
  "hey joey",
  "hey joie",
  "hey choi",
  "okay joi",
  "ok joi",
  "hi joi",
  "joi",
  "joey",
  "choi",
];

export type WakeMatch = {
  matched: boolean;
  /** Text after the wake phrase, original casing preserved. Empty for a bare wake. */
  command: string;
};

function normalizeWord(word: string): string {
  return word.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
}

function buildCandidates(phrase?: string): string[][] {
  const configured = (phrase ?? DEFAULT_WAKE_PHRASE).trim().toLowerCase();
  const unique = new Set<string>([configured, ...BUILTIN_ALIASES].filter(Boolean));
  return Array.from(unique)
    .map((candidate) => candidate.split(/\s+/).map(normalizeWord).filter(Boolean))
    .filter((words) => words.length > 0)
    // Longest phrases first so "hey joi" wins over the bare "joi".
    .sort((a, b) => b.length - a.length);
}

function matchesAt(words: string[], start: number, candidate: string[]): boolean {
  if (start + candidate.length > words.length) return false;
  for (let i = 0; i < candidate.length; i += 1) {
    if (words[start + i] !== candidate[i]) return false;
  }
  return true;
}

/**
 * Detect the wake phrase in a transcript.
 *
 * Returns `matched: true` with the trailing `command` when the phrase is found
 * (command is empty for a bare "Hey Joi"). Takes the earliest occurrence so a
 * command that follows the wake phrase is captured.
 */
export function detectWakeWord(transcript: string, phrase?: string): WakeMatch {
  const rawWords = transcript.trim().split(/\s+/).filter(Boolean);
  const normWords = rawWords.map(normalizeWord);
  if (normWords.every((word) => word === "")) {
    return { matched: false, command: "" };
  }

  const candidates = buildCandidates(phrase);
  for (let start = 0; start < normWords.length; start += 1) {
    if (normWords[start] === "") continue;
    for (const candidate of candidates) {
      if (matchesAt(normWords, start, candidate)) {
        const command = rawWords
          .slice(start + candidate.length)
          .join(" ")
          .replace(/^[\s,.:;!?-]+/, "")
          .trim();
        return { matched: true, command };
      }
    }
  }
  return { matched: false, command: "" };
}
