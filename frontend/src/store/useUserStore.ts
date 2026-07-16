import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UserStore {
  username: string | null;
  isDemo: boolean;
  setUsername: (name: string) => void;
  setIsDemo: (demo: boolean) => void;
}

export const useUserStore = create<UserStore>()(
  persist(
    (set) => ({
      username: null,
      isDemo: false,
      setUsername: (username) => set({ username }),
      setIsDemo: (isDemo) => set({ isDemo }),
    }),
    { name: 'sems-user' },
  ),
);
