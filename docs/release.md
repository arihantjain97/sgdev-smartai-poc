# Release Guide (SmartAI – Day4 flow)

## TL;DR
- **Content (packs) PRs** → CI runs lint/build/offline-eval. **No deploy**.
- After merge, a human runs **Promote Pack** (manual workflow) to publish **approved** docs to Azure AI Search.
- **API code** merges to `main` → **Run-from-Zip** auto-deploys App Service (Oryx disabled).
- **Rollback** = re-deploy the last successful `api_bundle.zip` artifact.

---

## 1) Content changes (packs)
**Who:** content owners / engineers  
**Paths:** `app/vault/**` (packs live at app/vault/), `tools/**`

1. Create PR with template edits.
2. CI **must pass**:
   - `CI Packs`: lint (schema + PAS/SCQA), build payload, offline eval (goldens).
3. Merge PR.
4. Publish to Search:
   - GitHub → **Actions → Promote Pack → Run workflow**
   - Input `packs`, e.g. `psg@1.0.0,edg@1.0.1`
   - Wait for **Wire-check** to print expected counts (e.g., `psg 1.0.0 5`).
5. Verify with API (optional):
   - `GET /v1/debug/packs?pack=psg` shows sections.
   - Draft once; response header includes `x-prompt-pack: psg@1.0.0`.

> Note: Promotion is **manual by design** (governed content release).

---

## 2) API code changes
**Who:** engineers  
**Paths:** `app/**`, `requirements.txt`

1. Merge to `main`.
2. Workflow **API Run-from-Zip** auto-builds:
   - Vendors deps into `package/`, zips → `api_bundle.zip`, deploys.
3. Post-deploy smoke runs:
   - `GET /health` → 200
   - `GET /v1/debug/whereami` → correct index/config

> Path filters prevent `/vault/**` edits from redeploying the API.

---

## 3) Rollback
1. GitHub → Actions → last **API Run-from-Zip** that was green.
2. Download its `api_bundle.zip` artifact (or “Re-run job” to redeploy the same).
3. Re-deploy that artifact.
4. Confirm `/health` and `/v1/debug/whereami`.

---

## 4) Environments & secrets
- **App Service settings:** `SCM_DO_BUILD_DURING_DEPLOYMENT=false`, `WEBSITE_RUN_FROM_PACKAGE=1`.
- **Secrets (env: dev):** `AZURE_WEBAPP_PUBLISH_PROFILE`, `AZURE_SEARCH_ADMIN_KEY`, `AZURE_SEARCH_QUERY_KEY`.
- Future: add `qa`, `stage`, `prod` environments with their own publish profiles.

---

## 5) Quality gates (what makes a PR fail)
- Missing structure token (e.g., PAS lacking **Solve**).
- Golden eval fails: groundedness proxy < 0.8, length > cap, or latency > cap.
- Lint errors: missing required fields/labels in templates.

---

## 6) Responsibilities
- **Content owners:** maintain `/vault/**`, update goldens, run **Promote Pack** after merge.
- **Engineers:** maintain `/app/**`, review CI gates, monitor deploys, own rollback.

---

## 7) References
- Workflows:
  - `.github/workflows/ci-packs.yml`
  - `.github/workflows/promote-pack.yml`
  - `.github/workflows/api-runfromzip.yml`
- Runbooks:
  - `/docs/runbooks/rollback.md` (redeploy last `api_bundle.zip`)
  - `/docs/runbooks/promote-pack.md` (optional, one-pager “how to click”)