import { initializeApp } from "firebase/app";
import { getAuth, signInAnonymously } from "firebase/auth";
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
