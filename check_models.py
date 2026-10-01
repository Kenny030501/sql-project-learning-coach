import json

from backend.providers import model_catalog, provider_status

print(json.dumps(provider_status(), ensure_ascii=False, indent=2))
for provider in ("deepseek", "zhipu"):
    try:
        print(provider, model_catalog(provider))
    except ValueError as exc:
        print(provider, str(exc))
