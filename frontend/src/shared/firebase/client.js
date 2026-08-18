import { initializeApp } from "firebase/app";
import {
  getAuth,
  onAuthStateChanged,
  signInAnonymously,
  signInWithEmailAndPassword,
  signOut,
} from "firebase/auth";
import { getStorage } from "firebase/storage";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID,
};

const firebaseApp = initializeApp(firebaseConfig);

export const storage = getStorage(firebaseApp);
export const auth = getAuth(firebaseApp);

// Storage rules require request.auth != null but the app has no real login
// flow yet, so callers sign in anonymously before touching Storage. Cached
// so concurrent uploads trigger at most one sign-in call.
let signInPromise = null;

export function ensureAnonymousAuth() {
  if (auth.currentUser) {
    return Promise.resolve(auth.currentUser);
  }
  if (!signInPromise) {
    signInPromise = signInAnonymously(auth)
      .then((credential) => credential.user)
      .catch((error) => {
        signInPromise = null;
        throw error;
      });
  }
  return signInPromise;
}

// Admin login for the /operations dashboard - a real (non-anonymous)
// Firebase account, distinct from the anonymous sign-in above used for
// document uploads. Access is still enforced server-side (the backend
// checks the token's email against ADMIN_EMAILS); this only gates the UI.
export function signInAdmin(email, password) {
  return signInWithEmailAndPassword(auth, email, password);
}

export function signOutAdmin() {
  return signOut(auth);
}

// True only for a real logged-in account, never for the anonymous user the
// onboarding flow signs in as.
export function isAdminUser(user) {
  return Boolean(user && !user.isAnonymous && user.email);
}

export function watchAuthState(callback) {
  return onAuthStateChanged(auth, callback);
}

export async function getIdToken() {
  const user = auth.currentUser;
  if (!isAdminUser(user)) return null;
  return user.getIdToken();
}