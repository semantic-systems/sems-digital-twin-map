import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UserStore {
  username: string | null;
  setUsername: (name: string) => void;
}

export const useUserStore = create<UserStore>()(
  persist(
    (set) => ({
      username: null,
      setUsername: (username) => set({ username }),
    }),
    { name: 'sems-user' },
  ),
);
