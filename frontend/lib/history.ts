import type { ChatMessage } from "./types";

export interface SavedChat {
  id: string;
  title: string;
  updated: number;
  convId: string | null;
  messages: ChatMessage[];
}

const KEY = "plantbot.chats.v1";

export function loadChats(): SavedChat[] {
  try {
    const raw = localStorage.getItem(KEY);
    const v = raw ? JSON.parse(raw) : [];
    return Array.isArray(v) ? v : [];
  } catch {
    return [];
  }
}

export function saveChats(chats: SavedChat[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(chats));
  } catch {
    /* storage unavailable: app still works */
  }
}
