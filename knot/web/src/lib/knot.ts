/**
 * The knot's cryptography. Everything here runs on the phone; the server only ever sees
 * the salt, the settings and ciphertext.
 *
 *   phrase ──normalise──► Argon2id(salt) ──► 32 bytes ──► AES-GCM key (non-extractable)
 *
 * "Key check": a fixed string encrypted with the key when the knot is first tied. Decrypting
 * it later proves the phrase is right, without the server learning anything.
 */
import { deriveKeyBytes } from './argon'

export interface KdfParams {
  alg: 'argon2id'
  m: number // memory, KiB
  t: number // passes
  p: number // parallelism
  v: 1
}

/** 64 MiB, 3 passes: about a second on a recent iPhone. */
export const DEFAULT_KDF: KdfParams = { alg: 'argon2id', m: 65536, t: 3, p: 1, v: 1 }

/** What the server stores (all base64). Matches api/app/routes/knot.py. */
export interface KnotRecord {
  kdf_salt: string
  kdf_params: KdfParams
  key_check: string
  key_check_nonce: string
}

const enc = new TextEncoder()
const dec = new TextDecoder()
const CHECK = enc.encode('knot:v1:check')
const CHECK_AAD = enc.encode('knot-check')

/**
 * Two phones must turn "the same phrase" into the same bytes, even when one keyboard
 * capitalises the first letter, uses curly apostrophes, or adds a trailing space.
 * So: Unicode-normalise, straighten quotes and dashes, collapse spaces, lower-case.
 */
export function normalizePhrase(phrase: string): string {
  return phrase
    .normalize('NFKC')
    .replace(/[‘’‚‛′`´]/g, "'")
    .replace(/[“”„‟″]/g, '"')
    .replace(/[‐-―−]/g, '-')
    .trim()
    .replace(/\s+/g, ' ')
    .toLowerCase()
}

// ── base64 helpers ──

export function toB64(bytes: Uint8Array): string {
  let s = ''
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i])
  return btoa(s)
}

export function fromB64(b64: string): Uint8Array {
  const s = atob(b64)
  const out = new Uint8Array(s.length)
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i)
  return out
}

const random = (n: number) => crypto.getRandomValues(new Uint8Array(n))

// ── Keys ──

export async function deriveKey(phrase: string, salt: Uint8Array, params: KdfParams): Promise<CryptoKey> {
  const raw = await deriveKeyBytes(normalizePhrase(phrase), salt, params)
  try {
    // extractable: false → the raw bytes can never be read back out, even by this app.
    return await crypto.subtle.importKey('raw', raw, { name: 'AES-GCM' }, false, ['encrypt', 'decrypt'])
  } finally {
    raw.fill(0)
  }
}

/** First tie (or retie): new salt, new key, new check value. */
export async function createKnot(
  phrase: string,
  params: KdfParams = DEFAULT_KDF,
): Promise<{ key: CryptoKey; record: KnotRecord }> {
  const salt = random(16)
  const key = await deriveKey(phrase, salt, params)
  const nonce = random(12)
  const check = new Uint8Array(
    await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce, additionalData: CHECK_AAD }, key, CHECK),
  )
  return {
    key,
    record: { kdf_salt: toB64(salt), kdf_params: params, key_check: toB64(check), key_check_nonce: toB64(nonce) },
  }
}

/** Does this key open the check value? (i.e. is it the right phrase) */
export async function keyFits(key: CryptoKey, record: KnotRecord): Promise<boolean> {
  try {
    const plain = new Uint8Array(
      await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv: fromB64(record.key_check_nonce), additionalData: CHECK_AAD },
        key,
        fromB64(record.key_check),
      ),
    )
    return plain.length === CHECK.length && plain.every((b, i) => b === CHECK[i])
  } catch {
    return false // GCM authentication failed: wrong key
  }
}

/** Unlock with the phrase. Returns the key, or null when it's not the phrase you two tied. */
export async function openKnot(phrase: string, record: KnotRecord): Promise<CryptoKey | null> {
  const key = await deriveKey(phrase, fromB64(record.kdf_salt), record.kdf_params)
  return (await keyFits(key, record)) ? key : null
}

// ── Answers (used from Session 5) ──

/**
 * Seal an answer. `context` (e.g. `${roundId}:${userId}`) is bound in as associated data,
 * so a sealed answer can't be moved to another round or passed off as the other person's.
 */
export async function seal(key: CryptoKey, text: string, context: string) {
  const nonce = random(12)
  const ct = new Uint8Array(
    await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv: nonce, additionalData: enc.encode(context) },
      key,
      enc.encode(text),
    ),
  )
  return { ciphertext: toB64(ct), nonce: toB64(nonce) }
}

export async function unseal(key: CryptoKey, ciphertext: string, nonce: string, context: string): Promise<string> {
  const plain = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: fromB64(nonce), additionalData: enc.encode(context) },
    key,
    fromB64(ciphertext),
  )
  return dec.decode(plain)
}
