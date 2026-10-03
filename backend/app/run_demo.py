"""End-to-end run on a real company, saving everything to backend/results/<slug>/ (git-ignored).

    python -m app.run_demo --company Boeing --sector Defence      # news + web + X + Facebook (Serper + Apify credits)
    python -m app.run_demo --company Boeing --threads             # also Threads (~$0.7 per run)
    python -m app.run_demo --company Boeing --reuse               # re-analyze saved raw files, no scraper calls
    python -m app.run_demo --company Boeing --no-x --no-facebook  # skip sources

Files written:
    raw_<source>.json   what each service returned, untouched
    analyzed.json       every mention with severity / verdict / reason / negative flag from the LLM
    negative.json       only the negative ones, most severe first
    report.md           readable summary
"""
import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

from app.analysis import analyze, negative_queries, web_queries
from app.llm import model_for, pick_provider
from app.schemas.common import Classification
from app.schemas.companies import CompanyDraft
from app.schemas.feed import Mention
from app.schemas.common import Platform
from app.sources import apify
from app.sources.serper import DEMO_COMPANY, MOCK_COMPANY, search_news, search_web

RESULTS = Path(__file__).resolve().parents[1] / "results"
_RANK = {"high": 0, "medium": 1, "low": 2}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", default="Goldman Sachs")
    ap.add_argument("--sector", default="Banking", help="Banking | Defence | Fintech | Energy | Other")
    ap.add_argument("--country", default="United States", help="Global = no geo bias (international companies)")
    ap.add_argument("--local", action="store_true", help="also add local-language risk words for the country")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--threads", action="store_true", help="include Threads (expensive); off by default")
    ap.add_argument("--threads-raw", help="saved Threads actor response (JSON list) to use instead of a paid run")
    ap.add_argument("--no-web", action="store_true")
    ap.add_argument("--no-news", action="store_true")
    ap.add_argument("--no-x", action="store_true")
    ap.add_argument("--no-facebook", action="store_true")
    ap.add_argument("--no-threads", action="store_true")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--reuse", action="store_true", help="re-analyze the raw_*.json already saved, no scraper calls")
    args = ap.parse_args()

    provider = pick_provider([Classification.public])
    print("LLM provider:", provider, "| model:", model_for(provider))
    if provider != "cloud":
        raise SystemExit("cloud LLM not active: set OPENAI_API_KEY and OPENAI_MODEL")

    if args.company == "Goldman Sachs":
        company = DEMO_COMPANY
    elif args.company == "Bank Pekao":
        company = MOCK_COMPANY
    else:
        company = CompanyDraft(name=args.company, sector=args.sector, country=args.country)
    slug = re.sub(r"\W+", "_", args.company.lower()).strip("_")
    cid, now = slug, int(time.time() * 1000)
    out = RESULTS / slug
    out.mkdir(parents=True, exist_ok=True)
    queries = negative_queries(company, 12, local=args.local)
    social = {Platform.x: queries[:8], Platform.facebook: queries[:3], Platform.threads: queries[:1]}
    print("news queries:", queries)
    print("web queries:", web_queries(company))

    def save(name, data):
        (out / name).write_text(json.dumps(data, ensure_ascii=False, indent=2))

    mentions = []
    if args.reuse:
        now_ms = now
        for name in ("raw_news.json", "raw_web.json"):
            if (out / name).exists():
                mentions += [Mention.model_validate(m) for m in json.loads((out / name).read_text())]
        for platform in (Platform.x, Platform.facebook, Platform.threads):
            f = out / f"raw_{platform.value}.json"
            if f.exists():
                mentions += [m for i in json.loads(f.read_text()) if (m := apify.to_mention(i, platform, cid, now_ms))]
        print(f"reused saved raw data: {len(mentions)} mentions")
        args.no_news = args.no_web = args.no_x = args.no_facebook = True
        args.threads = args.threads_raw = False
    if not args.no_news:
        found = search_news(company, cid, period="3m", queries=queries)
        save("raw_news.json", [m.model_dump(mode="json") for m in found])  # already mapped to Mention
        mentions += found
        print(f"news: {len(found)}")
    if not args.no_web:
        found = search_web(company, cid, web_queries(company), period="3m")
        save("raw_web.json", [m.model_dump(mode="json") for m in found])
        mentions += found
        print(f"web (forums/reviews/reddit): {len(found)}")
    for platform, skip in ((Platform.x, args.no_x), (Platform.facebook, args.no_facebook)):
        if skip:
            continue
        items = [i for inp in apify.INPUTS[platform](company, social[platform], args.limit) for i in apify.run_actor(platform, inp)]
        save(f"raw_{platform.value}.json", items)
        mentions += [m for i in items if (m := apify.to_mention(i, platform, cid, now))]
        print(f"{platform.value}: {len(items)} raw items")
    if args.threads or args.threads_raw:
        if args.threads_raw:
            items = json.loads(Path(args.threads_raw).read_text())
        else:
            items = [i for inp in apify.INPUTS[Platform.threads](company, social[Platform.threads], args.limit) for i in apify.run_actor(Platform.threads, inp)]
        save("raw_threads.json", items)
        mentions += [m for i in items if (m := apify.to_mention(i, Platform.threads, cid, now))]
        print(f"threads: {len(items)} raw items")

    # drop duplicates and old posts, then analyze
    seen, fresh = set(), []
    for m in mentions:
        if m.id not in seen and m.at >= now - args.days * 86400_000:
            seen.add(m.id)
            fresh.append(m)
    print(f"{len(mentions)} mentions, {len(fresh)} after dedupe + {args.days}-day filter; analyzing...")

    rows = []
    for n, m in enumerate(fresh, 1):
        try:
            a, negative = analyze(m, company)
            rows.append({**a.model_dump(mode="json", by_alias=True), "negative": negative})
        except Exception as e:  # keep going: one bad article must not lose the run
            rows.append({**m.model_dump(mode="json", by_alias=True), "negative": False, "error": str(e)[:200]})
        print(f"  {n}/{len(fresh)} {m.platform.value} negative={rows[-1]['negative']}")
    rows.sort(key=lambda r: r["at"], reverse=True)
    negative = sorted((r for r in rows if r["negative"]), key=lambda r: (_RANK[r["severity"]], -r["at"]))
    save("analyzed.json", rows)
    save("negative.json", negative)

    failed = sum(1 for r in rows if "error" in r)
    if failed:
        print(f"WARNING: {failed}/{len(rows)} analyses failed, e.g. {next(r['error'] for r in rows if 'error' in r)}")
    per = Counter(r["platform"] for r in rows)
    per_neg = Counter(r["platform"] for r in negative)
    lines = [f"# {company.name}: {len(rows)} mentions, {len(negative)} negative, {failed} analysis errors\n", "| platform | total | negative |", "|---|---|---|"]
    lines += [f"| {p} | {per[p]} | {per_neg[p]} |" for p in per]
    lines.append("")
    for r in negative:
        lines += [f"## [{r['severity']}] {r['platform']} / {r['author']}", f"{r['text'][:300]}", f"- verdict: {r['verdict']}",
                  f"- why: {r['reason']}", f"- reach: {r['reach']}  {'**INJECTION**' if r['injection'] else ''}", f"- {r['url']}", ""]
    (out / "report.md").write_text("\n".join(lines))
    print(f"\nsaved to {out}")


if __name__ == "__main__":
    main()
