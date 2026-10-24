/**
 * Argon2id runs here, off the main thread: deriving a key takes about a second on a phone
 * (that slowness is the point — it makes guessing the phrase expensive), and doing it in a
 * worker keeps the knot animation smooth meanwhile.
 */
import { argon2id } from 'hash-wasm'

interface Job {
  id: number
  password: string
  salt: Uint8Array
  m: number
  t: number
  p: number
}

// The project's TypeScript setup types `self` as a window; inside a worker it's a worker scope.
const ctx = self as unknown as {
  onmessage: ((e: MessageEvent<Job>) => void) | null
  postMessage(message: unknown, transfer?: Transferable[]): void
}

ctx.onmessage = async (e) => {
  const { id, password, salt, m, t, p } = e.data
  try {
    const key = (await argon2id({
      password,
      salt,
      memorySize: m,
      iterations: t,
      parallelism: p,
      hashLength: 32,
      outputType: 'binary',
    })) as Uint8Array
    ctx.postMessage({ id, key }, [key.buffer as ArrayBuffer])
  } catch (err) {
    ctx.postMessage({ id, error: String(err) })
  }
}
