# 🐙 Argo CD (GitOps) Local Setup for drive-ops

This directory contains configurations for deploying a local GitOps environment using Argo CD. This allows us to automatically synchronize the state of the local Kubernetes cluster with our GitHub repository.

## 🛠 Prerequisites
* A running local Kubernetes cluster (we use `kind`).
* The `kubectl` CLI installed.
* The `docker` CLI for managing the cluster lifecycle.

## 🚀 Step 1: Install Argo CD
Create a dedicated namespace and install the base Argo CD components. 
*(We use `--server-side` and `--force-conflicts` to avoid CRD manifest size limit errors).*

```bash
kubectl create namespace argocd
kubectl apply -n argocd --server-side --force-conflicts -f [https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml](https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml)
```

### 🔐 Step 2: Access the Web UI

1. **Port-forward** to access the UI from your host machine (keep this command running in a separate terminal tab):
   ```bash
   kubectl port-forward svc/argocd-server -n argocd 8080:443
   ```
2. **Retrieve the automatically generated password** for the `admin` user:
   ```bash
   kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d && echo
   ```
3. **Open `https://localhost:8080`** in your browser (accept the self-signed certificate warning). **Login:** `admin`.

## 🌍 Step 3: Initialize the Root Application (App-of-Apps)

To make the cluster automatically track our repository, apply the root application:

```bash
kubectl apply -f infra/k8s/argocd/root-app.yaml
```

## 🧪 Step 4: Verify Automated Synchronization (Self-Healing Test)

To verify that GitOps is working and protecting the cluster from manual interventions:

1. Check for the presence of the test config pulled from Git:
   ```bash
   kubectl get configmap gitops-test
   ```
2. Simulate a failure by manually deleting it:
   ```bash
   kubectl delete configmap gitops-test
   ```
3. Immediately check again:
   ```bash
   kubectl get configmap gitops-test
   ```
Argo CD should automatically restore it within a few seconds!

## ⏸️ Step 5: Managing Local PC Resources

Since we are working locally, you don't need to keep the cluster running 24/7.

1. **Pause the cluster** (free up RAM/CPU):
   ```bash
   docker stop drive-ops-cluster-control-plane
   ```
2. **Resume work** (Argo CD will wake up and sync everything automatically):
   ```bash
   docker start drive-ops-cluster-control-plane
   ```
