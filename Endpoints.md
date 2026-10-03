Ось чиста, структурована специфікація API ProofGate (FastAPI / Supabase) без зазначення власників.

* Базовий шлях: /api/v1
* Автентифікація: Authorization: Bearer <supabase_jwt_token> (для всіх захищених шляхів)

---

### 1. Автентифікація та Користувач

* POST /api/v1/auth/login — Вхід користувача (email/password або обмін токена Google Sign-in).
* GET /api/v1/me — Отримання даних поточного користувача (роль: analyst / compliance, прив'язана організація).
* PUT /api/v1/me — Оновлення даних профілю користувача.

---

### 2. Організація та Документи (Knowledge Base)

* GET /api/v1/organization — Налаштування компанії (назва, ключові аліаси, сектор, теми моніторингу).
* PUT /api/v1/organization — Оновлення профілю організації та моніторингових правил.
* GET /api/v1/documents — Список завантажених документів зі статусами обробки (`processing`, ready, failed`) та рівнем доступу (`public, internal, confidential, `restricted`).
* POST /api/v1/documents/upload — Завантаження файлу (PDF/TXT) у Storage з вибором класифікації доступу та постановкою задачі на векторну індексацію.
* GET /api/v1/documents/{id}/url — Отримання тимчасового підписаного посилання (Signed URL) на перегляд файлу з урахуванням ролі користувача.
* DELETE /api/v1/documents/{id} — Видалення документа та відповідних векторних фрагментів.

---

### 3. Парсери та Збір даних (Ingestion Sources)

> Всі зібрані пости та статті зберігаються в єдину таблицю mentions із зазначенням джерела (`facebook`, twitter, `gnews`).

#### Facebook

* POST /api/v1/feed/sources/facebook/sync — Ручний або запланований запуск парсингу нових згадок у FB за ключовими словами.
* POST /api/v1/feed/sources/facebook/webhook — Прийом подій у реальному часі через Graph API Webhooks.
* GET /api/v1/feed/sources/facebook/status — Моніторинг працездатності парсера Facebook (валідність токена, дата останньої синхронізації).

#### Twitter / X

* POST /api/v1/feed/sources/twitter/sync — Запуск збору твітів через Twitter API за аліасами та темами ризику.
* GET /api/v1/feed/sources/twitter/status — Стан воркера Twitter, ліміти API та кількість зібраних постів.
* POST /api/v1/feed/sources/twitter/test-query — Тестовий запит до Twitter API для налагодження фільтрів без запису у базу.

#### Google News / Serper

* POST /api/v1/feed/sources/gnews/sync — Парсинг новин через Serper API або RSS-потік за запитами компанії.
* GET /api/v1/feed/sources/gnews/status — Перевірка доступності джерела та залишку пошукових кредитів.

---

### 4. Лайв фід та Дешборд (Live Feed & Dashboard)

* GET /api/v1/dashboard/summary — Агрегована зводка для віджетів дешборда (поточний рівень загрози, кількість згадок за 24г, активні кластери, дії, що очікують рішення).
* GET /api/v1/feed — Отримання сирого потоку згадок із фільтрацією за часом (`since_id`, `since_timestamp`), платформою (`platform`) та тональністю (`sentiment`).
* GET /api/v1/feed/{id} — Детальна інформація про конкретний пост чи новину.

---

### 5. Інциденти, Фактчекінг та ШІ-Контраргументи

* GET /api/v1/incidents — Список зафіксованих інформаційних інцидентів (фільтри за критичністю severity, статусом та прапорцем спроби маніпуляції `is_injection_attempt`).
* GET /api/v1/incidents/{id} — Деталі інциденту: прив'язаний кластер постів, виділені твердження (claims), внутрішні/зовнішні докази, чернетка відповіді та результати перевірки на витік даних (disclosure check).
* POST /api/v1/incidents/{id}/generate-counter-argument — Запуск LLM для синтезу статті-спростування на базі підібраних документів.
* PATCH /api/v1/incidents/{id}/draft — Збереження відредагованого тексту чернетки (автоматично оновлює хеш і скидає попереднє погодження).
* POST /api/v1/incidents/{id}/request-approval — Відправка чернетки на погодження (вимагає ролі compliance, якщо задіяні конфіденційні дані).
* POST /api/v1/incidents/{id}/approve — Підтвердження публікації уповноваженою особою з криптографічною фіксацією хешу тексту.
* POST /api/v1/incidents/{id}/publish — Переміщення затвердженого тексту у чергу відправки (`outbox`).
* POST /api/v1/incidents/{id}/resolve — Закриття або відхилення інциденту з фіксацією причини.

---

### 6. Пошук по компаніях та Звіти (Company Intel & Reports)

* GET /api/v1/companies/search — Автокомпліт і швидкий пошук компаній у внутрішній базі.
* POST /api/v1/companies/investigate — Експрес-збір згадок та генерація первинного огляду ризиків для сторонньої компанії без обов'язкового збереження.
* POST /api/v1/companies/track — Додавання нової компанії до постійного моніторингу.
* GET /api/v1/reports — Список збережених аналітичних звітів з фільтрацією за компанією, типом та статусом.
* POST /api/v1/reports — Запуск фонової генерації нового структурованого звіту за параметрами.
* GET /api/v1/reports/{id} — Отримання повного вмісту звіту (JSON/Markdown із висновками та графіками).
* PATCH /api/v1/reports/{id} — Внесення ручних коментарів чи правок до сформованого звіту.
* DELETE /api/v1/reports/{id} — Видалення збереженого звіту.
* GET /api/v1/reports/{id}/export — Експорт звіту у форматі PDF або Markdown.
* POST /api/v1/reports/{id}/share — Створення публічного тимчасового read-only посилання для перегляду звіту.

---

### 7. Аналітика (Analytics)

* GET /api/v1/analytics/trends — Динаміка активності атак та розподіл тональності за часом.
* GET /api/v1/analytics/narratives — Рейтинг найпоширеніших дезінформаційних тем і наративів.
* GET /api/v1/analytics/coordination-signals — Метрики скоординованості бот-мереж (частка нових акаунтів, текстові дублікати, синхронні сплески).
* GET /api/v1/analytics/ai-metrics — Метрики шлюзу безпеки: кількість заблокованих prompt injection, витрачені токени/вартість аналізу, затримка перевірок (p50/p95).

---

### 8. Сповіщення (Notifications)

* GET /api/v1/notifications — Список системних алертів (нові критичні інциденти, статус генерації звітів, запити на погодження).
* PATCH /api/v1/notifications/{id}/read — Позначити обране сповіщення прочитаним.
* POST /api/v1/notifications/mark-all-read — Позначити всі наявні сповіщення прочитаними.
