# Palladion API (FastAPI / Supabase)

Специфікація узгоджена з фронтендом (`frontend/src`). Типи та enum-значення відповідають `frontend/src/lib/mock.ts`.

* Базовий шлях: `/api/v1`
* Автентифікація: `Authorization: Bearer <supabase_jwt_token>` (для всіх шляхів, крім `POST /feed/sources/facebook/webhook`, який перевіряє підпис Meta)
* Час — Unix ms (`at`, `createdAt`), як у фронтенді.

## Enum-значення

| Поле | Значення |
|---|---|
| `platform` | `x`, `facebook`, `reddit`, `telegram`, `tiktok`, `linkedin`, `threads`, `news` |
| `severity` | `high`, `medium`, `low` |
| `verdict` | `contradicted_by_documents`, `supported_by_documents`, `insufficient_evidence`, `opinion` |
| `status` (згадка) | `new`, `responded`, `dismissed` |
| `classification` (документ) | `public`, `internal`, `confidential`, `restricted` |
| `status` (документ) | `processing`, `ready` (+ `failed` — UI показує як помилку обробки) |

## Моделі

**Company**
```
{ id, name, website, aliases[], sector, country, people[], topics[], documents: Doc[], createdAt }
```
**Doc** — `{ id, name, size, classification, status }`

**Mention (Post)**
```
{ id, companyId, platform, author, handle, text, at, severity, verdict, reason,
  reach, cluster: { size, accounts } | null, injection: boolean, status }
```
`injection` = виявлено прихований промпт-інʼєкшн у кластері (блокується шлюзом безпеки).

---

### 1. Автентифікація та користувач

Вхід — **тільки Google**. Фронтенд викликає Supabase Auth напряму (`supabase.auth.signInWithOAuth({ provider: 'google' })`, вихід — `supabase.auth.signOut()`); окремих `/auth/login` і `/auth/logout` в API немає. Інші способи входу вимкнені в Supabase (`supabase/config.toml`), реєстрацію не через Google блокує тригер у БД, а API відхиляє токени з `app_metadata.provider != "google"` (403).

* `GET /me` — поточний користувач `{ name, email, role }` (`analyst` / `compliance`). Роль і організація беруться з claims `user_role` / `organization_id`, які додає custom access token hook.

---

### 2. Компанії (відстежувані)

Користувач може відстежувати кілька компаній (Onboarding wizard, сторінка Companies, «Track another company»).

* `GET /companies` — список компаній користувача з документами.
* `POST /companies` — створення компанії `{ name, website, aliases[], sector, country, people[], topics[] }`.
* `GET /companies/{id}` — одна компанія.
* `PUT /companies/{id}` — оновлення профілю та тем моніторингу.
* `DELETE /companies/{id}` — припинити моніторинг.
* `GET /companies/meta` — довідники для форм: `sectors` з рекомендованими `topics` на сектор (Banking, Defence, Fintech, Energy, Other) та список `countries`.

---

### 3. Документи (Knowledge Base)

Документи належать компанії.

* `GET /companies/{id}/documents` — документи зі статусом обробки та класифікацією.
* `POST /companies/{id}/documents` — завантаження (multipart: PDF/TXT, `classification` для кожного файлу); ставить задачу на векторну індексацію.
* `PATCH /documents/{id}` — зміна `classification`.
* `GET /documents/{id}/url` — тимчасове підписане посилання на перегляд (з урахуванням ролі).
* `DELETE /documents/{id}` — видалення документа та векторних фрагментів.

---

### 4. Лайв-фід згадок (Live Feed)

Одиниця роботи у UI — згадка (пост/стаття): блок «Needs attention» (high severity, `status=new`) і таблиця «All mentions».

* `GET /mentions` — потік згадок. Фільтри: `company_id`, `severity`, `platform`, `status`, `since_timestamp`, `since_id`, `limit`. Для «живого» оновлення UI опитує з `since_id` (або SSE `GET /mentions/stream`).
* `GET /mentions/{id}` — згадка з деталями (verdict, reason, cluster, injection).
* `PATCH /mentions/{id}/status` — `{ status: "new" | "responded" | "dismissed" }` (кнопка Dismiss, завершення відповіді).

Збір даних (внутрішньо, воркери) пише в єдину таблицю `mentions`; `platform` приймає всі значення з enum вище.

---

### 5. Відповідь на згадку (Counter-post)

Діалог «Create counter-post»: перевірка твердження, використані докази, чернетка, disclosure check.

* `GET /mentions/{id}/response` — поточний стан відповіді:
  ```
  { claimCheck: { verdict, reason },
    evidence: [{ docId, name, classification }],   // restricted документи не використовуються
    draft: string,
    disclosure: { needsCompliance: boolean, reason },
    injectionBlocked: boolean,
    approval: { state: "none" | "pending" | "approved", by, at } }
  ```
* `POST /mentions/{id}/response/generate` — генерація чернетки (LLM) на основі документів компанії; якщо документів немає — чернетка без фактичних тверджень.
* `PATCH /mentions/{id}/response/draft` — збереження відредагованого тексту (скидає попереднє погодження, оновлює хеш).
* `POST /mentions/{id}/response/approve` — «Approve response»: підтвердження аналітиком, якщо `needsCompliance=false`; фіксація хешу тексту. Виставляє `status=responded`.
* `POST /mentions/{id}/response/request-approval` — «Request approval»: відправка на погодження ролі `compliance`, якщо задіяні `confidential` документи.
* `POST /mentions/{id}/response/decision` — рішення compliance `{ approve: boolean, comment }` (тільки роль `compliance`).

Кнопка «Copy» — суто клієнтська.

---

### 6. Аналітика (Analytics)

Параметри для всіх: `company_id` (необовʼязково, за замовчуванням усі), `range` (за замовчуванням `24h`).

* `GET /analytics/summary` — лічильники плиток: відкриті згадки за severity, `responded`, `dismissed`, кількість кластерів, заблоковані інʼєкції.
* `GET /analytics/mentions-by-hour` — 24 погодинні бакети `{ hour, low, medium, high }` («Mentions by priority»).
* `GET /analytics/reach-by-platform` — `[{ platform, mentions, reach }]` («Reach by platform»).
* `GET /analytics/claim-verification` — розподіл verdict для згадок medium/high («Claim verification»).

---

### 7. Сповіщення (дзвіночок «Latest incidents»)

* `GET /notifications` — останні відкриті інциденти (high severity згадки, запити на погодження) `{ id, mentionId, title, severity, at, read }`; лічильник відкритих у відповіді (`openCount`).
* `PATCH /notifications/{id}/read` — позначити прочитаним.
* `POST /notifications/mark-all-read` — позначити всі прочитаними.

---

### 8. Джерела даних (службові, без UI)

Адмін/воркери; фронтенд їх не викликає.

* `POST /feed/sources/{platform}/sync` — запуск збору для `facebook`, `x`, `news` (Serper/RSS) та ін.
* `POST /feed/sources/facebook/webhook` — події Graph API.
* `GET /feed/sources/{platform}/status` — стан парсера (токен, остання синхронізація, ліміти).

---

### 9. Заплановано (UI поки немає)

* Звіти: `GET/POST /reports`, `GET/PATCH/DELETE /reports/{id}`, `GET /reports/{id}/export`, `POST /reports/{id}/share`.
* Дослідження сторонніх компаній: `GET /companies/search`, `POST /companies/investigate`.
* Профіль: `PUT /me`.
* Розширена аналітика: `GET /analytics/narratives`, `/analytics/coordination-signals`, `/analytics/ai-metrics`.
* Публікація: `POST /mentions/{id}/response/publish` (черга `outbox`).
