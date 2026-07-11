# Hops'n'Vectors developer shortcuts (GUD-004).
COMPOSE := docker compose
PSQL    := $(COMPOSE) exec postgres psql -U beer -d beer

.PHONY: up tui psql demo reset test lint down

up:            ## build and start the full stack
	$(COMPOSE) up --build

tui:           ## interactive beer recommender
	$(COMPOSE) run --rm scheduler tui

psql:          ## interactive psql session
	$(PSQL)

demo:          ## run all numbered demo scripts in order
	@for f in demo/0*.sql; do \
		echo "=== $$f ==="; \
		$(PSQL) -v ON_ERROR_STOP=1 -f - < $$f || exit 1; \
	done

reset:         ## wipe volumes and start fresh
	$(COMPOSE) down -v
	$(COMPOSE) up --build

test:          ## run unit tests inside the scheduler image
	$(COMPOSE) run --rm --entrypoint sh -v ./app/hopsnvectors:/app/hopsnvectors:ro -v ./app/tests:/app/tests:ro scheduler \
		-c "pip install -q pytest && cd /app && python -m pytest tests -k 'not integration'"

lint:          ## ruff-lint the Python package and tests
	$(COMPOSE) run --rm --entrypoint sh -v ./app/hopsnvectors:/app/hopsnvectors:ro -v ./app/tests:/app/tests:ro scheduler \
		-c "pip install -q ruff && cd /app && python -m ruff check hopsnvectors/ tests/"

down:          ## stop the stack (keep volumes/model cache)
	$(COMPOSE) down
