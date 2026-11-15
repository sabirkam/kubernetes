# Recipes are single commands so they run the same in cmd (Windows) and sh (Linux/macOS).
CLUSTER  ?= demo
VERSION  ?= v1
PYTHON   ?= python

.PHONY: cluster build load deploy status update rollback watch test smoke clean

cluster:
	kind create cluster --config kind-config.yaml
	kubectl get nodes -o wide

build:
	docker build -t demo-backend:$(VERSION) --build-arg APP_VERSION=$(VERSION) backend
	docker build -t demo-frontend:$(VERSION) --build-arg APP_VERSION=$(VERSION) frontend

load:
	kind load docker-image demo-backend:$(VERSION) demo-frontend:$(VERSION) --name $(CLUSTER)

deploy:
	kubectl apply -f k8s/
	kubectl rollout status deployment/backend
	kubectl rollout status deployment/frontend

status:
	kubectl get nodes,deployments,services,pods -o wide

update:
	$(MAKE) build load VERSION=v2
	kubectl set image deployment/backend backend=demo-backend:v2
	kubectl rollout status deployment/backend

rollback:
	kubectl rollout history deployment/backend
	kubectl rollout undo deployment/backend
	kubectl rollout status deployment/backend

watch:
	$(PYTHON) scripts/watch.py

test:
	$(PYTHON) -m pytest backend
	$(PYTHON) -m pytest frontend

smoke:
	$(PYTHON) -m pytest -v tests/smoke

clean:
	kind delete cluster --name $(CLUSTER)
