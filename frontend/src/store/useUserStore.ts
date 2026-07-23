import { create } from 'zustand';

/**
 * The authenticated user. Identity is owned by the httpOnly session cookie, not
 * this store — `username` here is just the resolved value from /auth/me (on load)
 * or /auth/login, kept in memory and re-derived on every reload. NOT persisted:
 * persisting it would let a logged-out client believe it's authenticated until a
 * request 401s. `authChecked` gates the initial render (login page vs app) until
 * the /auth/me probe has resolved.
 */
interface UserStore {
  username: string | null;
  authChecked: boolean;
  isDemo: boolean;
  setUsername: (name: string | null) => void;
  setAuthChecked: (v: boolean) => void;
  setIsDemo: (demo: boolean) => void;
}

export const useUserStore = create<UserStore>()((set) => ({
  username: null,
  authChecked: false,
  isDemo: false,
  setUsername: (username) => set({ username }),
  setAuthChecked: (authChecked) => set({ authChecked }),
  setIsDemo: (isDemo) => set({ isDemo }),
}));
