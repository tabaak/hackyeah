from pathlib import Path


def read_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    result = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip().strip("\"'")
    return result


requirements = {
    ".env": ("SUPABASE_URL",),
    "frontend/.env.local": ("VITE_SUPABASE_URL", "VITE_SUPABASE_PUBLISHABLE_KEY"),
}
missing = []
for filename, keys in requirements.items():
    values = read_env(Path(filename))
    missing.extend(f"{filename}: {key}" for key in keys if not values.get(key) or values[key].startswith("<"))

if missing:
    print("Missing or placeholder settings: " + "; ".join(missing))
    raise SystemExit(1)

print("Required Supabase settings are present.")
if not read_env(Path(".env")).get("SUPABASE_SERVICE_ROLE_KEY"):
    print("Warning: SUPABASE_SERVICE_ROLE_KEY is unset. UI/demo startup is allowed, but database-backed API endpoints will return 503 until it is added to .env.")
