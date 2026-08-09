import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  companyId: string | null;
  setTokens: (access: string, refresh: string) => void;
  setCompanyId: (id: string | null) => void;
  logout: () => void;
}

/** Tokens are persisted to localStorage so a reload does not sign the user out.
 *  This trades a little XSS exposure for usability, which is the normal call for an
 *  internal panel; moving to HttpOnly cookies is a backend change, not a UI one. */
export const useAuth = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      companyId: null,
      setTokens: (accessToken, refreshToken) => set({ accessToken, refreshToken }),
      setCompanyId: (companyId) => set({ companyId }),
      logout: () => set({ accessToken: null, refreshToken: null, companyId: null }),
    }),
    { name: "talento-auth" },
  ),
);

export const isAuthenticated = () => Boolean(useAuth.getState().accessToken);
