# Palladion API (FastAPI / Supabase)

Специфікація узгоджена з фронтендом (`frontend/web/src`). Типи та enum-значення відповідають `frontend/web/src/lib/domain.ts`.
Інтерактивна документація з усіма схемами: `http://localhost:8000/docs` (запуск бекенду — `backend/README.md`).

* Базовий шлях: `/api/v1` (локально `http://localhost:8000/api/v1`; CORS дозволено для `http://localhost:5173`, налаштовується `CORS_ORIGINS`).
* Автентифікація: `Authorization: Bearer <access_token>` для всіх шляхів, крім `POST /feed/sources/facebook/webhook`.
* JSON — camelCase. Час — Unix ms (`at`, `createdAt`, `expiresAt`, `lastSyncAt`).

## Підключення з фронтенду

Фронтенду потрібні `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` (Supabase → Project Settings → API Keys, **publishable/anon**, не secret) і адреса API.

```ts
import { createClient } from '@supabase/supabase-js'
export const supabase = createClient(import.meta.env.VITE_SUPABASE_URL, import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY)

// Вхід / вихід
await supabase.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: window.location.origin } })
await supabase.auth.signOut()

// Виклик API
async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { data } = await supabase.auth.getSession()
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { ...init.headers, Authorization: `Bearer ${data.session?.access_token}`,
               ...(init.body && !(init.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}) },
  })
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? res.statusText)
  return res.status === 204 ? (undefined as T) : res.json()
}
```

supabase-js сам оновлює токен; беріть його з `getSession()` перед кожним запитом.

## Помилки

Тіло помилки — `{ "detail": "<текст>" }` (для 422 — масив помилок валідації).

| Код | Коли |
|---|---|
| 401 | Немає токена, він прострочений або підроблений → вийти й увійти знову |
| 403 | Вхід не через Google; немає профілю (не ввімкнено token hook); дія лише для `compliance` |
| 404 | Обʼєкт не існує або належить іншій організації |
| 409 | Конфлікт стану: approve без потрібного погодження, рішення без запиту, чернетка змінилась |
| 413 / 415 | Файл більший за 5 МБ / не PDF чи TXT |
| 422 | Невалідне тіло або параметри |
| 501 / 503 | Конектор джерела не реалізований / не налаштований (тільки розділ 8) |

## Enum-значення

| Поле | Значення |
|---|---|
| `platform` | `x`, `facebook`, `reddit`, `telegram`, `tiktok`, `linkedin`, `bluesky`, `news` |
| `severity` | `high`, `medium`, `low` |
| `verdict` | `contradicted_by_documents`, `supported_by_documents`, `insufficient_evidence`, `opinion` |
| `status` (згадка) | `new`, `responded`, `dismissed` |
| `classification` (документ) | `public`, `internal`, `confidential`, `restricted` |
| `status` (документ) | `processing`, `ready`, `failed` (помилка обробки, напр. скан без текстового шару) |
| `sector` (компанія) | `Banking`, `Defence`, `Fintech`, `Energy`, `Other` |
| `role` | `analyst`, `compliance` |

## Моделі

**Company**
```
{ id, name, website, aliases[], sector, country, people[], topics[], logoUrl, documents: Doc[], createdAt }
```
**Doc** — `{ id, name, size /* байти */, classification, status, summary /* string або null */ }`

`summary` — ШІ-резюме документа (3–5 речень). `null`, поки `status` = `processing`, і для `restricted`, якщо роль не `compliance`.

**Mention (Post)**
```
{ id, companyId, platform, author, handle, text, at, severity, verdict, reason,
  reach, cluster: { size, accounts } | null, injection: boolean, status,
  url /* string або null: посилання на оригінал */, avatarUrl /* string або null: аватар автора */,
  images /* string[]: картинки допису або мініатюра статті; може бути порожнім */ }
```
`injection` = у тексті виявлено приховану інструкцію для ШІ; її проігноровано.

---

### 1. Автентифікація та користувач

Вхід — **тільки Google** через Supabase Auth (див. «Підключення»); `/auth/login` і `/auth/logout` в API немає. Інші способи входу вимкнені в Supabase, реєстрацію не через Google блокує тригер у БД, а API відхиляє токени з `app_metadata.provider != "google"` (403).

* `GET /me` — поточний користувач `{ name, email, role }`. Роль і організація беруться з claims `user_role` / `organization_id` токена; після зміни ролі користувач має вийти й увійти знову.

Новий користувач після першого входу отримує власну організацію і роль `analyst`.

---

### 2. Компанії (відстежувані)

Користувач може відстежувати кілька компаній (Onboarding wizard, сторінка Companies, «Track another company»).

* `GET /companies` — компанії організації з документами, від найстаршої.
* `POST /companies` → 201 — створення `{ name, website?, aliases?[], sector, country, people?[], topics?[] }`. При `DEMO_SEED=true` бекенд одразу додає 10 демо-згадок (з них 4 high); з `SERPER_API_KEY` у фоні збирає новини.
* `GET /companies/{id}` — одна компанія.
* `PUT /companies/{id}` — оновлення (повне тіло, як у POST).
* `PUT /companies/{id}/logo` — multipart поле `file`: PNG/JPG/WebP до 2 МБ. Сервер перевіряє й зменшує зображення та повертає `{ logoUrl }`. Логотип зберігається у приватному bucket `company-logos`; `GET /companies` також повертає підписане посилання `logoUrl` або `null`.
* `DELETE /companies/{id}/logo` → 204 — видалити логотип компанії.
* `DELETE /companies/{id}` → 204 — припинити моніторинг; видаляє також згадки, документи та файли компанії.
* `GET /companies/meta` — довідники для форм: `{ sectors: { [sector]: topics[] }, countries[] }` (ті ж значення, що `SECTORS` / `COUNTRIES` у фронтенді).

---

### 3. Документи (Knowledge Base)

Документи належать компанії.

* `GET /companies/{id}/documents` — документи зі статусом обробки та класифікацією.
* `POST /companies/{id}/documents` → 202 — завантаження multipart: поля `files` і `classifications`, по одній класифікації на файл, у тому ж порядку; PDF/TXT до 5 МБ, до 8 файлів за раз. Відповідь — `Doc[]` зі статусом `processing`; індексація та резюме йдуть у фоні (секунди), потім `ready` (з `summary`) або `failed` — оновіть список через `GET /companies` або `GET /companies/{id}/documents`.
  ```ts
  const form = new FormData()
  files.forEach(({ file, classification }) => { form.append('files', file); form.append('classifications', classification) })
  await api(`/companies/${id}/documents`, { method: 'POST', body: form })
  ```
* `PATCH /documents/{id}` — `{ classification }`.
* `GET /documents/{id}/url` — `{ url, expiresAt }`, підписане посилання на 5 хв; `restricted` — тільки для ролі `compliance` (інакше 403).
* `DELETE /documents/{id}` → 204 — видалення файлу та векторних фрагментів.

---

### 4. Лайв-фід згадок (Live Feed)

Одиниця роботи у UI — згадка (пост/стаття): блок «Needs attention» (high severity, `status=new`) і таблиця «All mentions».

* `GET /mentions` — згадки, нові зверху. Фільтри: `company_id`, `severity`, `platform`, `status`, `since_timestamp` (ms), `since_id`, `limit` (за замовчуванням 50, максимум 200).
  Рекомендоване «живе» оновлення: раз на 10–15 с `GET /mentions?limit=200` (так підтягуються і зміни статусів від колег).
* `GET /mentions/stream` — SSE: подія `mention` (data — обʼєкт Mention) для кожної нової згадки, перевірка кожні 5 с. Браузерний `EventSource` не вміє передавати заголовок `Authorization`, тож читайте потік через `fetch` + `ReadableStream` (або `@microsoft/fetch-event-source`) — або просто опитуйте `GET /mentions`.
* `GET /mentions/{id}` — одна згадка.
* `PATCH /mentions/{id}/status` — `{ status: "new" | "responded" | "dismissed" }` (кнопка Dismiss; `responded` виставляється автоматично після погодження відповіді).

Нові згадки з `severity=high` створюють сповіщення.

---

### 5. Відповідь на згадку (Counter-post)

Діалог «Create counter-post»: перевірка твердження, використані докази, чернетка, disclosure check.

* `GET /mentions/{id}/response` — поточний стан відповіді. **Перше відкриття генерує чернетку** — з LLM це може тривати кілька секунд, покажіть індикатор.
  ```
  { claimCheck: { verdict, reason },
    evidence: [{ docId, name, classification }],   // до 3 документів; restricted ніколи
    draft: string,
    disclosure: { needsCompliance: boolean, reason },
    injectionBlocked: boolean,
    approval: { state: "none" | "pending" | "approved", by: string | null, at: number | null } }
  ```
  `approval.by` — імʼя того, хто погодив; `approval.at` — час рішення (для `pending` — час запиту).
  Перевірка може уточнити `verdict` / `reason` згадки; перечитайте згадку, якщо показуєте їх у фіді.
* `POST /mentions/{id}/response/generate` — повторна генерація на основі документів компанії; скидає погодження. Якщо документів немає — чернетка без фактичних тверджень. Без доступного LLM — шаблонна чернетка.
* `PATCH /mentions/{id}/response/draft` — `{ text }`; збереження відредагованого тексту. Скидає попереднє погодження і заново робить disclosure check.
* `POST /mentions/{id}/response/revise` — `{ text, instruction }`; AI-переписування поточного тексту за інструкцією (тон, довжина, головна думка) з тими самими правилами (лише факти з документів). Зберігається як ручна правка; без доступного LLM — 503, текст не змінюється.
* `POST /mentions/{id}/response/approve` — «Approve response»: погодження поточного тексту (фіксується хеш), згадка → `responded`. Якщо `needsCompliance=true`, аналітик отримує 409 — треба `request-approval`; `compliance` може погодити напряму.
* `POST /mentions/{id}/response/request-approval` — «Request approval»: `approval.state` → `pending`, усі `compliance`-користувачі організації отримують сповіщення. Правка чернетки після запиту його скасовує.
* `POST /mentions/{id}/response/decision` — рішення compliance `{ approve: boolean, comment?: string }` (тільки роль `compliance`, інакше 403; без активного запиту — 409). Погодження → згадка `responded`; автор запиту отримує сповіщення. Відхилення повертає `approval.state` у `none`.

UI для ролей: аналітик бачить «Approve response», якщо `needsCompliance=false`, інакше «Request approval»; при `pending` — «Waiting for compliance». `compliance` при `pending` бачить «Approve» / «Reject». Кнопка «Copy» — суто клієнтська.

---

### 6. Аналітика (Analytics)

Параметри: `company_id` (необовʼязково, за замовчуванням усі), `range` = `24h` | `7d` | `30d` | `all` (за замовчуванням `24h`; `all` = за весь час; `mentions-by-hour` завжди 24 год). Рахуються згадки, опубліковані в межах `range`.

* `GET /analytics/summary` — `{ total, high, medium, low, openHigh, responded, dismissed, clusters, injectionsBlocked }`. Плитки: «Mentions · 24h» = `total`, «High priority · open» = `openHigh`, «Coordinated clusters» = `clusters`, «Responses approved» = `responded`.
* `GET /analytics/mentions-by-hour` — 24 погодинні бакети від найстаршого `{ hour: "HH:00", low, medium, high }`; `hour` — **UTC**, переведіть у локальний час для підписів.
* `GET /analytics/mentions-by-day?range=7d|30d` — 7 або 30 календарних днів (UTC), від найстаршого, `{ day: "YYYY-MM-DD", low, medium, high }`. Для графіків 7d/30d.
* `GET /analytics/reach-by-platform` — `[{ platform, mentions, reach }]` для всіх 7 платформ, за спаданням `reach`.
* `GET /analytics/claim-verification` — `[{ verdict, count }]` для згадок medium/high, усі 4 verdict.

---

### 7. Сповіщення (дзвіночок)

Сповіщення персональні.

* `GET /notifications?limit=20` (максимум 100) — `{ items: [{ id, kind, mentionId, title, severity, at, read }], openCount }`, нові зверху. `kind` = `critical_mention` | `approval_requested` | `approval_decided`; `title` — текст згадки (обрізайте в UI); `openCount` — кількість непрочитаних (бейдж). Клік → відкрити згадку `mentionId` і `PATCH …/read`.
* `PATCH /notifications/{id}/read` — позначити прочитаним, повертає Notification.
* `POST /notifications/mark-all-read` → 204.
* `POST /push-tokens` `{ token, platform }` → 204 — мобільний застосунок реєструє свій Expo push-токен (`ExponentPushToken[…]`, `platform` = `ios` | `android`) після входу. Токен прив'язується до поточного користувача; якщо пристрій увійшов в інший акаунт — переходить до нього. Сповіщення `critical_mention` додатково надсилаються push-ом на всі пристрої одержувача; токени видалених застосунків прибираються автоматично.
* `DELETE /push-tokens/{token}` → 204 — при виході з акаунта (лише свій токен).

---

### 8. Джерела даних (службові, без UI)

Адмін/воркери; фронтенд їх не викликає.

* `POST /feed/sources/{platform}/sync` → 202 `{ accepted, added }` — збір для всіх компаній організації. Усе йде у фоні: відповідь одразу, `added` = 0, нові згадки зʼявляються в стрічці за хвилини; поки попередній запуск тієї ж платформи не завершився — 409. `news` — Google News через Serper (10 статей на сторінку, `SERPER_PAGES` сторінок на запит; потрібен `SERPER_API_KEY`) плюс безкоштовний Google News RSS (до 100 статей, `NEWS_RSS`); без обох — 503. `x`, `facebook` — Apify (потрібен `APIFY_TOKEN`, інакше 503), коштує кредити; ліміт постів за запуск — `APIFY_LIMIT_X` / `_FACEBOOK`. До LLM потрапляють лише елементи з ознакою ризику (`LLM_ANALYSE_ALL=true` — усі).

**Автозапуск.** Бекенд сам повторює збір у фоні: `SYNC_NEWS_MINUTES` (60), `SYNC_X_MINUTES` (180), `SYNC_FACEBOOK_MINUTES` (720); `SYNC_ENABLED=false` вимикає все. Перший прохід — через `SYNC_STARTUP_DELAY_SECONDS` після старту, і лише для джерел, що не збирали дані протягом інтервалу (захист від перезапусків). Ручний `sync` ділить із ним один «слот» на організацію й платформу, тож запуски не дублюються. Історія новин (`NEWS_BACKFILL_DAYS`, 60 днів) довантажується один раз, коли в компанії ще немає статей старших за 14 днів; критичні сповіщення та push — лише для згадок не старших за `NOTIFY_MAX_AGE_HOURS` (72). Лишає лише пости, де згадано назву компанії чи її аліас (≥ 3 символи). Інші платформи — 501.
* `POST /feed/sources/facebook/webhook` — події Graph API (501, поки немає конектора; автентифікація підписом Meta, не JWT).
* `GET /feed/sources/{platform}/status` — `{ healthy, lastSyncAt, detail }`: чи налаштований конектор і коли платформа востаннє дала реальну (не демо) згадку.

---

### 9. Заплановано (ще не реалізовано)

* Звіти: `GET/POST /reports`, `GET/PATCH/DELETE /reports/{id}`, `GET /reports/{id}/export`, `POST /reports/{id}/share`.
* Дослідження сторонніх компаній: `GET /companies/search`, `POST /companies/investigate`.
* Профіль: `PUT /me`.
* Розширена аналітика: `GET /analytics/narratives`, `/analytics/coordination-signals`, `/analytics/ai-metrics`.
* Публікація: `POST /mentions/{id}/response/publish` (черга `outbox`).
