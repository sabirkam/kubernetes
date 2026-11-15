# Answers to the assignment questions

## 1. What are the basic parts of a Kubernetes cluster?

A cluster consists of a **control plane**, which decides what should run, and **worker nodes**, which run it. Everything is driven by declarative objects. You describe the desired state, and controllers keep changing the actual state until it matches.

**Control plane** (in this repo: `demo-control-plane`, visible via `kubectl get pods -n kube-system`)

| Component | Role |
|---|---|
| kube-apiserver | The only entry point to the cluster: a REST API used by `kubectl`, controllers and kubelets. |
| etcd | Key-value store holding the whole cluster state. |
| kube-scheduler | Assigns new pods to nodes, taking resources, taints and spread/affinity rules into account. |
| kube-controller-manager | Reconciliation loops, e.g. Deployment → ReplicaSet → Pods, node health, endpoints. |

**Every node** (in this repo: `demo-worker`, `demo-worker2`)

| Component | Role |
|---|---|
| kubelet | Agent that starts the node's pods through the container runtime and runs their probes. |
| container runtime | Actually runs the containers (containerd in kind and AKS). |
| kube-proxy | Programs the Service virtual IPs (iptables/IPVS) so traffic reaches the pods. |
| CNI plugin | Pod networking: every pod gets its own IP and can reach every pod on any node (kindnet here; Azure CNI on AKS). |

**Core objects used here:** *Pod* (one or more containers sharing an IP), *ReplicaSet* (keeps N identical pods), *Deployment* (manages ReplicaSets and rollouts), *Service* (stable name and virtual IP in front of pods selected by label), *labels/selectors* (how these objects find each other). CoreDNS resolves Service names, so `frontend` reaches the backend at `http://backend:8000`. Other common objects are ConfigMap/Secret, Ingress, Namespace, PersistentVolume and HorizontalPodAutoscaler.

## 2. How does a Kubernetes cluster differ from Red Hat OpenShift?

OpenShift **is** Kubernetes: a certified distribution plus an opinionated platform on top of it. Kubernetes manifests such as the ones in `k8s/` run on both. The differences are what comes in the box and the defaults.

| | Kubernetes (upstream / AKS) | OpenShift (OCP, on Azure: ARO) |
|---|---|---|
| Scope | Orchestration core; you choose ingress, registry, CI, monitoring, auth | Integrated platform: registry, monitoring, logging, OAuth, web console, OperatorHub |
| Security defaults | Permissive unless you add Pod Security Admission / policies | Strict *Security Context Constraints*: containers run under a random non-root UID by default |
| External access | Ingress (controller of your choice) | *Route* objects with the built-in HAProxy router (Ingress also supported) |
| Builds & images | Outside the cluster (CI builds and pushes images) | In-cluster builds (BuildConfig, Source-to-Image) and ImageStreams |
| Multi-tenancy | Namespace | *Project* (namespace + default RBAC/quotas) |
| CLI | `kubectl` | `oc` (a superset of `kubectl`) |
| Lifecycle & support | Community releases or a managed service (AKS) | Red Hat release cadence, OS (RHCOS) managed by the platform, commercial support |

For this app the main practical point is security: the images already run as a non-root user (`USER 10001`) and the app files are readable by group 0. OpenShift's default `restricted` SCC replaces the UID with a random one but keeps group 0, so the same images would run there without changes.

## 3. How would the application be deployed from the repository to the cluster?

```
git push ─► CI: unit tests ─► docker build ─► push image (tag = commit SHA) to registry ─► CD: update cluster ─► rollout + smoke test
```

1. **Repository.** It contains the application code, the Dockerfiles and the manifests (`k8s/`). Changes go through pull requests with review.
2. **CI** ([.github/workflows/ci.yaml](../.github/workflows/ci.yaml)). On every PR it runs `pytest` and test-builds the images. On merge to `main` it builds both images and pushes them to a registry, tagged with the immutable commit SHA. Here the registry is GHCR; on Azure it would be **Azure Container Registry**, with images scanned for vulnerabilities.
3. **CD**, one of two models:
   - **Push:** the pipeline logs in to AKS (OIDC federated identity, so no stored secrets), runs `kubectl apply` and sets the new image tag. A sketch is in the commented `deploy` job of the workflow.
   - **GitOps (preferred for production):** the pipeline only commits the new tag to the manifests (or a config repo, typically with Kustomize overlays per environment). **Argo CD / Flux** in the cluster pulls the change and applies it. Git is then the single source of truth: drift is detected, every change is audited, and a rollback is a `git revert`.
4. **Promotion.** The same image (same SHA) moves dev → staging → prod. Only the configuration differs between environments.
5. **Verification.** The pipeline waits for `kubectl rollout status` and runs a smoke test (here `tests/smoke`). If the rollout fails, it rolls back.

Locally the same flow is `make test build load deploy smoke`. `kind load` stands in for the registry push.

## 4. How would a rolling update be realized?

A rolling update replaces the pods of a Deployment a few at a time. Old and new versions serve traffic side by side, and a Service only sends traffic to pods that are ready (Figure 2). It is started by changing the pod template, usually the image tag:

```bash
kubectl set image deployment/backend backend=demo-backend:v2   # or: edit the manifest + kubectl apply
kubectl rollout status deployment/backend                      # wait / watch
kubectl rollout undo deployment/backend                        # roll back to the previous ReplicaSet
```

What happens (3 replicas, `maxSurge: 1`, `maxUnavailable: 0`):

1. The Deployment controller creates a new ReplicaSet for v2 and scales it to 1. Now 4 pods run (3× v1, 1× v2).
2. The scheduler places the new pod according to the spread constraint. Its readiness probe must pass, and the pod must stay ready for `minReadySeconds`. Only then does the Service add it to its endpoints.
3. The controller scales the old ReplicaSet down by one. The terminating pod is removed from the endpoints, waits in `preStop`, then receives `SIGTERM` and finishes its in-flight requests.
4. Steps 1–3 repeat until all 3 pods run v2. The old ReplicaSet is kept with 0 replicas as a rollback target (`kubectl rollout history`).

The settings that make it work, in [k8s/backend.yaml](../k8s/backend.yaml) (the same in `frontend.yaml`):

| Setting | Line | Why |
|---|---|---|
| `strategy: RollingUpdate`, `maxSurge: 1`, `maxUnavailable: 0` | [12–16](../k8s/backend.yaml#L12-L16) | Add one new pod before removing an old one, so capacity never drops below 3 ready pods. |
| `minReadySeconds: 3` | [17](../k8s/backend.yaml#L17) | A new pod must stay ready for a while before the rollout continues. This catches pods that crash right after start. |
| `readinessProbe` on `/health` | [47](../k8s/backend.yaml#L47) | The Service sends traffic only to pods that are ready. A broken v2 never becomes ready and the rollout stops, while v1 keeps serving. |
| `livenessProbe` | [52](../k8s/backend.yaml#L52) | Restarts a container that hangs. |
| `lifecycle.preStop.sleep: 5` | [59](../k8s/backend.yaml#L59) | Gives kube-proxy on every node time to remove the pod from the endpoints before it stops, so in-flight connections don't fail. |
| `topologySpreadConstraints` | [23](../k8s/backend.yaml#L23) | Keeps pods spread across nodes, also while old and new pods run side by side, so one node failure never takes down all replicas. |
| Immutable image tag (`demo-backend:v1` → `v2`) | [33](../k8s/backend.yaml#L33) | The pod template changes, which triggers the rollout. Rollback means going back to a known image. |

**Verified:** `make watch` during `make update` gave 309 requests and 0 errors, and during `make rollback` 130 requests and 0 errors. [tests/smoke/test_rolling_update.py](../tests/smoke/test_rolling_update.py) asserts the same.

Alternatives when side-by-side versions are not acceptable: `strategy: Recreate` (stop all old pods, then start the new ones, which means downtime), **blue/green** (run a full second Deployment, then switch the Service selector), or **canary** (send a small share of traffic to the new version, e.g. with Argo Rollouts or a service mesh).
