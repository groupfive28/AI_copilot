import { createContext, useContext, useEffect, useState } from "react";

import { isAdminUser, watchAuthState } from "../../shared/firebase/client.js";

const AuthContext = createContext({ user: null, loading: true });

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    return watchAuthState((firebaseUser) => {
      setUser(isAdminUser(firebaseUser) ? firebaseUser : null);
      setLoading(false);
    });
  }, []);

  return <AuthContext.Provider value={{ user, loading }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
