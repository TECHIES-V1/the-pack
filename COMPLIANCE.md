# COMPLIANCE.md — Qwen Cloud Global AI Hackathon

> Status: **DRAFT — needs two sign-offs** (Doc 05 §02). Answers below are sourced from the
> official rules; items marked ⚠️ need the team to verify/decide before the gate closes.
>
> Official rules: https://qwencloud-hackathon.devpost.com/rules
> Hackathon home: https://qwencloud-hackathon.devpost.com
> Last verified against the rules page: **2026-06-13**

## The answers (Doc 05 §02 checklist)

### 1. Eligibility — Nigeria and each member's country
The rules exclude residents of any country where **QwenCloud registration is not
supported** or that is under applicable **sanctions**. Nigeria is **not named** as
excluded. ⚠️ **This is not a clear yes** — it hinges on whether QwenCloud account
registration succeeds from Nigeria (the same blocker as risk **R1**). Verify by completing
signup + billing from Nigeria (Doc 05 §01). Each member confirms their own country of
residence is not sanctioned/unsupported.

### 2. Team size limits
**Teams of 1–5 members.** Pack's roster (Doc 05 §06) is within this. One member is the
authorized **Representative** (the team lead) who allocates any prize.

### 3. Pre-existing code policy
Projects must be **newly created**, or if pre-existing, **significantly updated after the
submission period start (May 26, 2026)**. Pack is built fresh in June — clean. Any
third-party SDK/API/data must be used under its license/terms.
- ✅ **The Qwen voice model is a pre-existing external service** — permitted, *provided it
  is authorized under its terms and **disclosed***. We disclose it explicitly in the
  write-up and here. (Mitigates **R6**.)
- ✅ Borrowed patterns (Magentic-One, LangGraph, Qwen-Agent, Letta, Open Agent Builder)
  are permissively licensed; we adapt patterns, we do not vendor the repos. See
  `docs/BORROWING.md`.

### 4. Open-source & repo-access requirements
The repo **must be public and open source, with a detectable LICENSE file visible in the
About section.** ✅ Added: root `LICENSE` (MIT). This **answers Open Question #5** in the
PRD: yes, a public open-source repo is required (not judge-access-only). ⚠️ Ensure the
GitHub repo is flipped to **public** before submission and the license shows in About.

### 5. IP and prize terms
Entrants **retain ownership** of their submission. The sponsor gets a **non-exclusive
license** to use it for judging and for promoting/documenting the hackathon. For teams,
the **Representative allocates the prize** among members. ✅ No conflict with our plans.

### 6. Required deliverables
- **Demo video < 3 minutes**, showing the project functioning, on **YouTube/Vimeo/Youku**
  (public). (Doc 01: record by Jul 5.)
- **Public open-source code repository** with a detectable license + setup instructions.
- **Text description** of features and functionality.
- **Proof of deployment on Alibaba Cloud** — the rules want **a link to a code file in the
  repo that demonstrates use of Alibaba Cloud services/APIs.** ⚠️ Note: this is *in
  addition to* the screen recording the PACK docs plan. Do **both**: keep the deployment
  code path obvious in-repo (e.g. `backend/app/config.py` + deploy manifests) **and**
  record the proof video.
- **Architecture diagram** (event-bus spine front and center).
- **Track selection.**

### 7. Qwen / Alibaba usage requirements (which APIs count)
Must use **Qwen models on Qwen Cloud (Model Studio / DashScope)** and **deploy on Alibaba
Cloud**. We run all inference through the Qwen OpenAI-compatible endpoint (F14) and deploy
the engine + gateway on Alibaba Cloud (Doc 04 §07). ⚠️ Confirm the exact **track name**:
the PACK docs say "Agent Society Track"; the live Devpost lists named tracks (e.g.
MemoryAgent, AI Showrunner). Pick/confirm the correct track and note it here.

### 8. Submission timezone
**Deadline: July 9, 2026, 2:00 pm Pacific Time.** Controlling timezone is **Pacific Time**,
not Lagos. 2:00 pm PT ≈ **23:00 WAT (Lagos)** on July 9. We submit **July 8** (Doc 01) —
a full day of buffer. Deadlines bite in the organizer's timezone.

## Sign-offs (two required)
- [X] Sign-off 1: Tobi (Team Lead Sign-off)-Approved for Backend & Schema Alignment 
- [X] Sign-off 2: Eyitayo (Frontend Lead Sign Off)-Approved for Frontend Canvas Alignment 

## Open verification items before the gate

- [ ] **R1/Eligibility:** QwenCloud signup + billing succeeds from Nigeria.
- [ ] Repo flipped **public**; LICENSE visible in the About section.
- [ ] Exact **track** confirmed and recorded above.
- [ ] Qwen voice model authorized under its terms (Tobi, contract by Jun 16).
