# Palladion mobile

Expo (SDK 57) + Expo Router app for critical notifications. It uses the same design as `frontend/`.

```bash
cd mobile
cp .env.example .env.local   # same Supabase values as frontend/.env.local
npm install
npm start          # then press i / a / w, or scan the QR code with Expo Go
npm run typecheck
```

## Open in Xcode

The iOS Bundle Identifier is `com.mshupeikin.palladion`, with Apple team `368P9H47N6`.

Generate the native project and install CocoaPods from `mobile/`:

```bash
npx expo prebuild --platform ios
```

Open `ios/Palladion.xcworkspace` in Xcode. Select the **Palladion** target → **Signing & Capabilities**, use **Automatically manage signing**, and select the **Yevgen Shupeikin** team. The `expo-notifications` plugin adds **Push Notifications** during prebuild.

For a device build, select your iPhone as the run destination in Xcode. Native `ios/` files are generated locally and ignored by Git; keep the identifier and team in `app.json` so subsequent prebuilds preserve them.

## Sign-in

Google through Supabase, the same accounts as the web app. The app opens Google in an in-app browser (PKCE). The session is saved on the device and refreshed while the app is open.

The redirect URLs have to be on Supabase's allow list:
- **Hosted project:** Dashboard → Authentication → URL Configuration → Redirect URLs. Add `palladion://**` (builds) and `exp://**` (Expo Go during development).
- **Local Supabase:** already in `supabase/config.toml`.

A 401 or 403 from the API (expired token, profile not provisioned) signs the user out and shows the reason on the login screen.

## Layout

- `src/app/login.tsx`: Google sign-in, ported from `frontend/src/pages/Login.tsx`
- `src/app/index.tsx`: notifications inbox. Live from `/notifications`: polls every 12 s in the foreground, plus pull to refresh, mark read and mark all read
- `src/app/settings.tsx`: theme picker (Graphite, Navy, Laurel, Light)
- `src/lib/session.tsx`, `src/lib/supabase.ts`: session state and the OAuth flow
- `src/lib/theme.ts`: design tokens ported from `frontend/src/index.css`. **Keep these in sync.**
- `src/components/ui.tsx`: Button, Badge, SeverityBadge and LogoMark, matching `frontend/src/lib/ui.tsx`
- `src/lib/notifications.ts`: types mirroring `backend/app/schemas/notifications.py`, plus the API calls

`EXPO_PUBLIC_API_URL=http://localhost:8000/api/v1` works in the iOS Simulator. On a physical phone, use your Mac's LAN IP and run the backend with `--host 0.0.0.0`.

## Push notifications

`critical_mention` notifications are also pushed to the phone through Expo's push service. Approval notifications stay in-app only.

- **App:** after sign-in, the app asks for permission and registers its Expo push token with `POST /push-tokens`. Before sign-out it removes it with `DELETE /push-tokens/{token}`. While the app is open, an incoming push shows as a banner and reloads the inbox (`src/lib/push.ts`).
- **Backend:** `notify()` → `app/services/push.py`. Delivery is best effort: if a push fails, the in-app notification is still saved. Tokens of uninstalled apps are deleted automatically.

**One-time setup:**
1. **Database:** apply `supabase/migrations/20261003220000_push_tokens.sql` to the Supabase project.
2. **EAS project:** `app.json` already links `@magorr/palladion` to project `3154c216-2109-46af-ba4d-135c3347b454`. Sign in with `npx eas-cli login` to manage its credentials. Expo push tokens need this project id.
3. **iOS delivery:** run `npx eas-cli credentials --platform ios` to set up an APNs key. An existing Apple `.p8` key can be uploaded with its Key ID and Team ID. This needs a paid Apple Developer account. Android needs FCM credentials the same way.
4. **Rebuild:** `expo-notifications` is native code, so rebuild with `npx expo run:ios` after adding it.

**Testing on the simulator without APNs:**
```bash
xcrun simctl push booted com.mshupeikin.palladion path/to/critical.apns
```
with a payload like `{"aps":{"alert":{"title":"Critical mention","body":"…"},"sound":"default"},"body":{"kind":"critical_mention"}}`.
