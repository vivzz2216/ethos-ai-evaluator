/**
 * IndexedDB-based chat persistence layer.
 * Stores all agent chat sessions locally in the browser.
 * No external database needed.
 */

const DB_NAME = 'ethos_agent_chats';
const DB_VERSION = 1;
const STORE_CHATS = 'chats';
const STORE_MESSAGES = 'messages';

export interface StoredChat {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  model: string;
  messageCount: number;
  preview: string;       // last message preview
  pinned: boolean;
}

export interface StoredMessage {
  id: string;
  chatId: string;
  role: 'user' | 'assistant' | 'tool' | 'status' | 'error';
  content: string;
  timestamp: number;
  toolCalls?: any[];
}

// ── Open DB ──────────────────────────────────────────────────────────

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);

    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_CHATS)) {
        const chatStore = db.createObjectStore(STORE_CHATS, { keyPath: 'id' });
        chatStore.createIndex('updatedAt', 'updatedAt', { unique: false });
        chatStore.createIndex('pinned', 'pinned', { unique: false });
      }
      if (!db.objectStoreNames.contains(STORE_MESSAGES)) {
        const msgStore = db.createObjectStore(STORE_MESSAGES, { keyPath: 'id' });
        msgStore.createIndex('chatId', 'chatId', { unique: false });
        msgStore.createIndex('timestamp', 'timestamp', { unique: false });
      }
    };

    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

// ── Chat CRUD ────────────────────────────────────────────────────────

export async function createChat(id: string, title: string, model: string): Promise<StoredChat> {
  const db = await openDB();
  const chat: StoredChat = {
    id,
    title,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    model,
    messageCount: 0,
    preview: '',
    pinned: false,
  };
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_CHATS, 'readwrite');
    tx.objectStore(STORE_CHATS).put(chat);
    tx.oncomplete = () => resolve(chat);
    tx.onerror = () => reject(tx.error);
  });
}

export async function getChat(id: string): Promise<StoredChat | null> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_CHATS, 'readonly');
    const req = tx.objectStore(STORE_CHATS).get(id);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}

export async function updateChat(id: string, updates: Partial<StoredChat>): Promise<void> {
  const db = await openDB();
  const existing = await getChat(id);
  if (!existing) return;
  const updated = { ...existing, ...updates, updatedAt: Date.now() };
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_CHATS, 'readwrite');
    tx.objectStore(STORE_CHATS).put(updated);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function deleteChat(id: string): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction([STORE_CHATS, STORE_MESSAGES], 'readwrite');
    tx.objectStore(STORE_CHATS).delete(id);
    // Delete all messages for this chat
    const msgStore = tx.objectStore(STORE_MESSAGES);
    const idx = msgStore.index('chatId');
    const range = IDBKeyRange.only(id);
    const cursor = idx.openCursor(range);
    cursor.onsuccess = () => {
      const c = cursor.result;
      if (c) { c.delete(); c.continue(); }
    };
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function getAllChats(): Promise<StoredChat[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_CHATS, 'readonly');
    const req = tx.objectStore(STORE_CHATS).index('updatedAt').getAll();
    req.onsuccess = () => {
      // Sort: pinned first, then by updatedAt descending
      const chats = (req.result as StoredChat[]).sort((a, b) => {
        if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
        return b.updatedAt - a.updatedAt;
      });
      resolve(chats);
    };
    req.onerror = () => reject(req.error);
  });
}

export async function searchChats(query: string): Promise<StoredChat[]> {
  const all = await getAllChats();
  const q = query.toLowerCase();
  return all.filter(c =>
    c.title.toLowerCase().includes(q) ||
    c.preview.toLowerCase().includes(q)
  );
}

// ── Message CRUD ─────────────────────────────────────────────────────

export async function saveMessage(msg: StoredMessage): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_MESSAGES, 'readwrite');
    tx.objectStore(STORE_MESSAGES).put(msg);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function saveMessages(msgs: StoredMessage[]): Promise<void> {
  if (msgs.length === 0) return;
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_MESSAGES, 'readwrite');
    const store = tx.objectStore(STORE_MESSAGES);
    for (const msg of msgs) {
      store.put(msg);
    }
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function getMessages(chatId: string): Promise<StoredMessage[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_MESSAGES, 'readonly');
    const idx = tx.objectStore(STORE_MESSAGES).index('chatId');
    const req = idx.getAll(IDBKeyRange.only(chatId));
    req.onsuccess = () => {
      const msgs = (req.result as StoredMessage[]).sort((a, b) => a.timestamp - b.timestamp);
      resolve(msgs);
    };
    req.onerror = () => reject(req.error);
  });
}

// ── Helpers ──────────────────────────────────────────────────────────

export function generateTitle(firstMessage: string): string {
  // Take first ~50 chars of the first user message as title
  const cleaned = firstMessage.replace(/\n/g, ' ').trim();
  if (cleaned.length <= 50) return cleaned;
  return cleaned.slice(0, 47) + '...';
}

export function formatTimestamp(ts: number): string {
  const d = new Date(ts);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
