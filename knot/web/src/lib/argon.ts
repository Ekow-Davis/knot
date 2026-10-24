/** Talks to the Argon2id worker. One worker, reused; jobs matched by id. */

let worker: Worker | null = null
let nextId = 1
const pending = new Map<number, { resolve: (k: Uint8Array) => void; reject: (e: Error) => void }>()

function getWorker(): Worker {
  if (!worker) {
    worker = new Worker(new URL('./argon.worker.ts', import.meta.url), { type: 'module' })
    worker.onmessage = (e: MessageEvent<{ id: number; key?: Uint8Array; error?: string }>) => {
      const job = pending.get(e.data.id)
      if (!job) return
      pending.delete(e.data.id)
      if (e.data.key) job.resolve(e.data.key)
      else job.reject(new Error(e.data.error ?? 'Key derivation failed'))
    }
    worker.onerror = (e) => {
      for (const job of pending.values()) job.reject(new Error(e.message || 'Key derivation failed'))
      pending.clear()
      worker?.terminate()
      worker = null
    }
  }
  return worker
}

/** Argon2id(password, salt) → 32 raw key bytes. */
export function deriveKeyBytes(
  password: string,
  salt: Uint8Array,
  params: { m: number; t: number; p: number },
): Promise<Uint8Array> {
  return new Promise((resolve, reject) => {
    const id = nextId++
    pending.set(id, { resolve, reject })
    getWorker().postMessage({ id, password, salt, m: params.m, t: params.t, p: params.p })
  })
}
