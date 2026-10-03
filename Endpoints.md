# Palladion API (FastAPI / Supabase)

Специфікація узгоджена з фронтендом (`frontend/src`). Типи та enum-значення відповідають `frontend/src/lib/mock.ts`.
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
| `platform` | `x`, `facebook`, `reddit`, `telegram`, `tiktok`, `linkedin`, `threads`, `news` |
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
{ id, name, website, aliases[], sector, country, people[], topics[], documents: Doc[], createdAt }
```
**Doc** — `{ id, name, size /* байти */, classification, status, summary /* string або null */ }`

`summary` — ШІ-резюме документа (3–5 речень). `null`, поки `status` = `processing`, і для `restricted`, якщо роль не `compliance`.

**Mention (Post)**
```
{ id, companyId, platform, author, handle, text, at, severity, verdict, reason,
  reach, cluster: { size, accounts } | null, injection: boolean, status, url /* string або null: посилання на оригінал */ }
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
* `POST /mentions/{id}/response/approve` — «Approve response»: погодження поточного тексту (фіксується хеш), згадка → `responded`. Якщо `needsCompliance=true`, аналітик отримує 409 — треба `request-approval`; `compliance` може погодити напряму.
* `POST /mentions/{id}/response/request-approval` — «Request approval»: `approval.state` → `pending`, усі `compliance`-користувачі організації отримують сповіщення. Правка чернетки після запиту його скасовує.
* `POST /mentions/{id}/response/decision` — рішення compliance `{ approve: boolean, comment?: string }` (тільки роль `compliance`, інакше 403; без активного запиту — 409). Погодження → згадка `responded`; автор запиту отримує сповіщення. Відхилення повертає `approval.state` у `none`.

UI для ролей: аналітик бачить «Approve response», якщо `needsCompliance=false`, інакше «Request approval»; при `pending` — «Waiting for compliance». `compliance` при `pending` бачить «Approve» / «Reject». Кнопка «Copy» — суто клієнтська.

---

### 6. Аналітика (Analytics)

Параметри: `company_id` (необовʼязково, за замовчуванням усі), `range` = `24h` | `7d` | `30d` (за замовчуванням `24h`; `mentions-by-hour` завжди 24 год). Рахуються згадки, опубліковані в межах `range`.

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

---

### 8. Джерела даних (службові, без UI)

Адмін/воркери; фронтенд їх не викликає.

* `POST /feed/sources/{platform}/sync` → 202 `{ accepted, added }` — збір для всіх компаній організації. Реалізовано: `news` (Google News через Serper, потрібен `SERPER_API_KEY`, інакше 503). Інші платформи — 501, поки немає конектора.
* `POST /feed/sources/facebook/webhook` — події Graph API (501, поки немає конектора; автентифікація підписом Meta, не JWT).
* `GET /feed/sources/{platform}/status` — `{ healthy, lastSyncAt, detail }`: чи налаштований конектор і коли платформа востаннє дала реальну (не демо) згадку.

---

### 9. Заплановано (ще не реалізовано)

* Звіти: `GET/POST /reports`, `GET/PATCH/DELETE /reports/{id}`, `GET /reports/{id}/export`, `POST /reports/{id}/share`.
* Дослідження сторонніх компаній: `GET /companies/search`, `POST /companies/investigate`.
* Профіль: `PUT /me`.
* Розширена аналітика: `GET /analytics/narratives`, `/analytics/coordination-signals`, `/analytics/ai-metrics`.
* Публікація: `POST /mentions/{id}/response/publish` (черга `outbox`).
