.PHONY: api web demo pipeline test lint build

api:
	cd apps/api && uv run uvicorn demandsense.main:app --reload

web:
	cd apps/web && pnpm dev

demo:
	cd apps/api && uv run demandsense build-demo --output ../../artifacts/demo

pipeline:
	cd apps/api && uv run demandsense pipeline --input ../../data/raw/Online-Retail.xlsx --output ../../artifacts --data-mode "UCI Online Retail"

test:
	cd apps/api && uv run pytest
	cd apps/web && pnpm test

lint:
	cd apps/api && uv run ruff check src tests
	cd apps/web && pnpm lint

build:
	cd apps/web && pnpm build
