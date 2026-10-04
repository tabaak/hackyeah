"""Repeat the tiny live OpenJev smoke without Qwen, Supabase or a cloud key.

Exit 0: both labeled smoke decisions correct. Exit 1: semantic failure.
Exit 2: provider/contract unavailable. This is not a representative quality evaluation.
"""
import argparse
import json
from pathlib import Path

from .config import Settings
from .providers import Decisions, ProviderError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = Settings()
    provider = Decisions("openjev", config.openjev_model, config.openjev_url, timeout=30)
    questions = {
        "sensitive": {"type": "noul", "instructions": "Does this text contain a private credential?"},
        "kind": {"type": "choice", "instructions": "Which subject is discussed?",
                 "criteria": {"birds": "Birds and nature", "finance": "Financial services"}},
    }
    samples = [("neutral_bird", "A kestrel is a bird of prey.", False),
               ("synthetic_credential", "FICTIONAL API_KEY=synthetic-do-not-send-12345.", True)]
    report = {"mode": "live", "inputs": "synthetic", "representativeQualityClaim": False, "results": []}
    code = 0
    for name, state, expected in samples:
        try:
            result = provider.evaluate(state, questions)
            correct = (result.data["sensitive"]["noul"] >= .5) == expected
            report["results"].append({"inputKind": name, "model": result.model, "answers": result.data,
                                      "usage": result.usage, "durationMs": result.duration_ms,
                                      "expectedSensitive": expected, "privacySmokeCorrect": correct})
            if not correct:
                code = 1
        except ProviderError:
            report["results"].append({"inputKind": name, "error": "provider_or_contract_unavailable"})
            code = 2
            break
    report["privacySmokePassed"] = code == 0
    report["decisionThresholdForSmokeOnly"] = .5
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")
    print(text)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
