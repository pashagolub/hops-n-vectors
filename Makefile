# Hops'n'Vectors developer shortcuts (GUD-004).
COMPOSE := docker compose
PSQL    := $(COMPOSE) exec postgres psql -U beer -d beer

.PHONY: up tui psql demo reset test lint down logs

up:            ## build and start the full stack
	$(COMPOSE) up --build

tui:           ## interactive beer recommender
	$(COMPOSE) run --rm scheduler tui

psql:          ## interactive psql session
	$(PSQL)

logs:		 ## show logs for all containers
	$(COMPOSE) logs -f

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

# ---------------------------------------------------------------------------
# Workshop image (workshop/) - a single self-contained container for attendees.
# ---------------------------------------------------------------------------
WORKSHOP_IMAGE ?= ghcr.io/pashagolub/hops-n-vectors:pg18

.PHONY: workshop-build workshop-run workshop-verify workshop-psql workshop-save workshop-clean

workshop-build: ## build the attendee image from workshop/db/*.sql.gz
	docker build -f workshop/Dockerfile -t $(WORKSHOP_IMAGE) .

workshop-run:  ## run the attendee image exactly as an attendee would
	-docker rm -fv beer
	docker run -d --name beer -p 5432:5432 $(WORKSHOP_IMAGE)

workshop-verify: ## assert the image contract and run every exercise twice
	bash scripts/workshop-verify.sh beer

workshop-psql: ## psql into the running workshop container
	docker exec -it beer psql

workshop-save: ## write USB tarballs for amd64 and arm64 into dist/
	bash scripts/workshop-save.sh $(WORKSHOP_IMAGE)

workshop-clean: ## remove the attendee container and its volume
	-docker rm -fv beer
