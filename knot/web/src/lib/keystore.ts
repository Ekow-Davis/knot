/**
 * "Remember on this phone": the knot key kept in IndexedDB.
 *
 * What's stored is the CryptoKey object itself, created non-extractable. The browser keeps the
 * key material internally; neither this app nor anything else on the page can read the bytes.
 * Clearing site data, signing out, or a retie on the other phone all make it go away.
 */

const DB = 'knot'
const STORE = 'keys'
const ID = 'knot'

export interface StoredKey {
  key: CryptoKey
  version: number
  userId: string
}

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1)
    req.onupgradeneeded = () => req.result.createObjectStore(STORE)
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function run<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open()
  try {
    return await new Promise<T>((resolve, reject) => {
      const tx = db.transaction(STORE, mode)
      const req = fn(tx.objectStore(STORE))
      tx.oncomplete = () => resolve(req.result)
      tx.onerror = () => reject(tx.error)
      tx.onabort = () => reject(tx.error)
    })
  } finally {
    db.close()
  }
}

export async function loadKey(): Promise<StoredKey | null> {
  try {
    return ((await run('readonly', (s) => s.get(ID))) as StoredKey | undefined) ?? null
  } catch {
    return null // private browsing, storage blocked: behave as "not remembered"
  }
}

export async function saveKey(value: StoredKey): Promise<boolean> {
  try {
    await run('readwrite', (s) => s.put(value, ID))
    return true
  } catch {
    return false
  }
}

export async function clearKey(): Promise<void> {
  try {
    await run('readwrite', (s) => s.delete(ID))
  } catch {
    /* nothing stored */
  }
}
