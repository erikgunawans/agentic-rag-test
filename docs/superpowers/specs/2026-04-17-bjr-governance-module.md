# BJR Decision Governance Module — Design Spec

**Date**: 2026-04-17
**Author**: BD & Strategic Partnership + Engineering
**Status**: Draft
**Source Document**: `Matriks_Regulasi_GCG_BJR_Ancol_2026.docx`

---

## Context

PT Pembangunan Jaya Ancol Tbk operates under **two simultaneous legal regimes**: corporate law (UU PT, OJK, BEI) as a publicly-listed company, and regional finance law (PP BUMD, Pergub DKI) as a BUMD owned by Pemprov DKI Jakarta. This duality means business losses risk being reclassified as *kerugian keuangan daerah*, potentially criminalizing legitimate business decisions.

The **Business Judgment Rule (BJR)** — codified in UU PT Art. 97(5) and reinforced by UU No. 1/2025 and PP 23/2022 — protects directors from personal liability if they can prove decisions were made with good faith, no conflict of interest, and proper due diligence. However, this protection requires **systematic documentation** across three phases (Pre-Decision, Decision, Post-Decision) with evidence tied to specific regulatory requirements.

LexCore currently provides document-centric tools (compliance checks, contract analysis, obligation tracking). This module introduces a **decision-centric governance layer** that orchestrates those existing tools around the BJR lifecycle, transforming LexCore from a document analysis platform into a **decision governance platform** for Ancol.

---

## Scope

### In Scope
- BJR decision lifecycle tracking (Pre-Decision → Decision → Post-Decision → Completed)
- Configurable regulation database (seeded with 28 Ancol-specific regulations across 4 layers)
- Configurable checklist templates (seeded with 16 items across 3 phases)
- Evidence attachment with polymorphic linking to existing LexCore entities (documents, tool results, approvals)
- LLM-assisted evidence assessment with confidence scoring and HITL review
- Phase-gated approvals using existing approval workflow infrastructure
- GCG Compliance Matrix (11 aspects with indicators, frequency, PIC)
- Strategic risk register (global + per-decision risks)
- BJR dashboard with aggregate metrics
- Full audit trail integration
- Admin CRUD for regulatory items, checklist templates, GCG aspects
- i18n (Indonesian + English)

### Out of Scope
- Automated regulatory crawling (existing regulatory intelligence module handles this separately)
- External auditor read-only portal (future enhancement)
- Document generation from BJR templates (can use existing document creation tool)
- Integration with external systems (Dokmee, Google Workspace)

---

## Data Model

### Table 1: `bjr_regulatory_items`

The 4-layer regulation database. Configurable by admins, seeded with Ancol's 28 regulations.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | uuid | PK, default gen_random_uuid() | |
| `code` | text | NOT NULL | e.g. "UU No. 40/2007" |
| `title` | text | NOT NULL | e.g. "Undang-Undang Perseroan Terbatas" |
| `layer` | text | CHECK in ('uu', 'pp', 'pergub', 'ojk_bei', 'custom') | Regulatory layer |
| `substance` | text | | Relevance description for Ancol |
| `url` | text | | Link to official document source |
| `critical_notes` | text | | e.g. "Kritis untuk BJR Ancol" |
| `is_active` | boolean | DEFAULT true | Soft delete |
| `created_by` | uuid | FK → auth.users | |
| `created_at` | timestamptz | DEFAULT now() | |
| `updated_at` | timestamptz | DEFAULT now() | |

**Indexes**: `layer`, `is_active`
**RLS**: All authenticated users can read active items. Admins can insert/update.
**Seed data**: 28 regulations (6 UU + 3 PP + 14 Pergub/KepGub + 5 OJK/BEI)

### Table 2: `bjr_checklist_templates`

Configurable checklist items organized by BJR phase.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | uuid | PK | |
| `phase` | text | CHECK in ('pre_decision', 'decision', 'post_decision') | |
| `item_order` | int | NOT NULL | Display order within phase |
| `title` | text | NOT NULL | e.g. "Due Diligence telah dilakukan secara komprehensif" |
| `description` | text | | Detailed requirement description |
| `regulatory_item_ids` | uuid[] | | References to bjr_regulatory_items |
| `is_required` | boolean | DEFAULT true | Required for phase completion |
| `is_active` | boolean | DEFAULT true | |
| `created_by` | uuid | FK → auth.users | |
| `created_at` | timestamptz | DEFAULT now() | |

**Indexes**: `phase`, `is_active`
**RLS**: All authenticated users can read. Admins can insert/update.
**Seed data**: 16 items (5 pre_decision + 6 decision + 5 post_decision) from Ancol BJR checklist

### Table 3: `bjr_decisions`

Each strategic business decision as a lifecycle entity.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | uuid | PK | |
| `user_id` | uuid | FK → auth.users, NOT NULL | Creator (Direksi) |
| `user_email` | text | NOT NULL | Display convenience (matches audit_logs pattern) |
| `title` | text | NOT NULL | Decision title |
| `description` | text | | Business context and rationale |
| `decision_type` | text | CHECK in ('investment', 'procurement', 'partnership', 'divestment', 'capex', 'policy', 'other') | |
| `current_phase` | text | CHECK in ('pre_decision', 'decision', 'post_decision', 'completed') | DEFAULT 'pre_decision' |
| `status` | text | CHECK in ('draft', 'in_progress', 'under_review', 'approved', 'completed', 'cancelled') | DEFAULT 'draft' |
| `risk_level` | text | CHECK in ('critical', 'high', 'medium', 'low') | |
| `estimated_value` | numeric | | Transaction value (IDR) for materiality thresholds |
| `bjr_score` | float | DEFAULT 0.0 | Overall checklist completeness (0-100) |
| `gcg_aspect_ids` | uuid[] | | Which GCG aspects this decision touches |
| `metadata` | jsonb | DEFAULT '{}' | Flexible fields (board members involved, related RKAB item, etc.) |
| `completed_at` | timestamptz | | When all phases completed |
| `created_at` | timestamptz | DEFAULT now() | |
| `updated_at` | timestamptz | DEFAULT now() | Trigger-managed |

**Indexes**: `user_id`, `current_phase`, `status`, `created_at DESC`
**RLS**: Users see own decisions. Admins see all.
**Trigger**: `updated_at` auto-update on row change.

### Table 4: `bjr_evidence`

Evidence attachments linking decisions to checklist items and existing LexCore entities.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | uuid | PK | |
| `decision_id` | uuid | FK → bjr_decisions, NOT NULL | |
| `checklist_item_id` | uuid | FK → bjr_checklist_templates, NOT NULL | Which requirement this evidence satisfies |
| `evidence_type` | text | CHECK in ('document', 'tool_result', 'manual_note', 'approval', 'external_link') | |
| `reference_id` | uuid | | Polymorphic FK → documents, document_tool_results, approval_requests, etc. |
| `reference_table` | text | | 'documents', 'document_tool_results', 'approval_requests' |
| `title` | text | NOT NULL | Display name |
| `notes` | text | | User's justification |
| `file_path` | text | | Supabase Storage path (for direct uploads) |
| `external_url` | text | | For external_link type |
| `llm_assessment` | jsonb | | LLM evaluation: {satisfies: bool, assessment: str, gaps: [str]} |
| `confidence_score` | float | | 0.0-1.0 |
| `review_status` | text | DEFAULT 'not_assessed' | 'not_assessed' (no LLM run yet), 'auto_approved' (LLM confident), 'pending_review' (LLM low confidence → HITL), 'approved', 'rejected' |
| `attached_by` | uuid | FK → auth.users | |
| `created_at` | timestamptz | DEFAULT now() | |

**Indexes**: `decision_id`, `checklist_item_id`, `review_status`
**RLS**: Users see evidence on own decisions. Admins see all.

### Table 5: `bjr_gcg_aspects`

The 11-aspect GCG Compliance Matrix.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | uuid | PK | |
| `aspect_name` | text | NOT NULL | e.g. "Tata Kelola Organ" |
| `regulatory_item_ids` | uuid[] | | References to bjr_regulatory_items |
| `indicators` | text[] | | Compliance indicator descriptions |
| `frequency` | text | CHECK in ('per_transaction', 'monthly', 'quarterly', 'annually') | |
| `pic_role` | text | | Responsible role/department |
| `is_active` | boolean | DEFAULT true | |
| `created_by` | uuid | FK → auth.users | |
| `created_at` | timestamptz | DEFAULT now() | |

**Seed data**: 11 GCG aspects (Tata Kelola Organ, Rencana Bisnis, Pengadaan B/J, Investasi & Capex, Laporan Keuangan, Keterbukaan Informasi, Audit Internal, Komite Audit, Remunerasi Organ, LHKPN & Integritas, BJR Documentation)

### Table 6: `bjr_risk_register`

Strategic risk tracking — both standing (global) and per-decision risks.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | uuid | PK | |
| `decision_id` | uuid | FK → bjr_decisions | NULL for global/standing risks |
| `risk_title` | text | NOT NULL | |
| `description` | text | | Full risk description |
| `risk_level` | text | CHECK in ('critical', 'high', 'medium', 'low') | |
| `mitigation` | text | | Mitigation strategy |
| `status` | text | CHECK in ('open', 'mitigated', 'accepted', 'closed') | DEFAULT 'open' |
| `owner_role` | text | | Who owns the risk |
| `is_global` | boolean | DEFAULT false | true = standing risk applicable to all decisions |
| `created_by` | uuid | FK → auth.users | |
| `created_at` | timestamptz | DEFAULT now() | |
| `updated_at` | timestamptz | DEFAULT now() | |

**Seed data**: 4 standing risks (Dualisme Rezim Hukum [HIGH], Keputusan di Luar RKAB [HIGH], Transisi Kepemimpinan [MEDIUM], Disclosure Tidak Tepat Waktu [MEDIUM])

---

## Backend Architecture

### Router: `backend/app/routers/bjr.py`

Prefix: `/bjr`

#### Decision Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/decisions` | User | Create new BJR decision |
| GET | `/decisions` | User | List decisions (filterable: phase, status, type, date) |
| GET | `/decisions/{id}` | User | Full detail: decision + checklist progress + evidence + risks |
| PATCH | `/decisions/{id}` | User (owner) | Update decision metadata |
| DELETE | `/decisions/{id}` | User (owner) | Cancel decision (set status='cancelled') |

#### Evidence Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/decisions/{id}/evidence` | User | Attach evidence (FormData: file upload OR reference_id + reference_table) |
| DELETE | `/evidence/{evidence_id}` | User | Remove evidence attachment |
| POST | `/evidence/{evidence_id}/assess` | User | Trigger LLM assessment of evidence against checklist item |

#### Phase Progression
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/decisions/{id}/submit-phase` | User (owner) | Submit current phase for approval → creates approval_request |
| GET | `/decisions/{id}/phase-status` | User | Check approval status of current phase |

Phase advancement is triggered synchronously inside `approvals.py` when an approval action with `resource_type='bjr_phase'` is approved. The handler calls a `bjr_advance_phase()` function that updates `current_phase` and `status` on the decision. No polling needed.

#### Risk Register
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/risks` | User | List risks (global + decision-specific) |
| POST | `/risks` | User | Create risk |
| PATCH | `/risks/{id}` | User | Update risk |

#### Admin CRUD
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/regulatory-items` | User | List regulations (filterable by layer) |
| POST | `/regulatory-items` | Admin | Create regulation |
| PATCH | `/regulatory-items/{id}` | Admin | Update regulation |
| GET | `/checklist-templates` | User | List checklist items (filterable by phase) |
| POST | `/checklist-templates` | Admin | Create checklist item |
| PATCH | `/checklist-templates/{id}` | Admin | Update checklist item |
| GET | `/gcg-aspects` | User | List GCG aspects |
| POST | `/gcg-aspects` | Admin | Create GCG aspect |
| PATCH | `/gcg-aspects/{id}` | Admin | Update GCG aspect |

#### Dashboard
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/summary` | User | Aggregate stats: decisions by phase, risk distribution, checklist completeness, GCG coverage |

### Service: `backend/app/services/bjr_service.py`

#### LLM Evidence Assessment

```python
class BJREvidenceAssessment(BaseModel):
    satisfies_requirement: bool
    assessment: str  # Explanation of how evidence meets/fails the requirement
    gaps: list[str]  # Missing elements or weaknesses
    regulatory_alignment: str  # How this aligns with cited regulations
    confidence_score: float = 0.0

@traceable(name="bjr_evidence_assessment")
async def assess_evidence(
    evidence_text: str,
    checklist_item_title: str,
    checklist_item_description: str,
    regulatory_references: list[str],
    decision_context: str,
) -> BJREvidenceAssessment:
```

**System prompt** instructs the LLM to:
1. Evaluate whether the evidence document satisfies the specific BJR checklist requirement
2. Reference the cited regulatory articles (e.g., PP 23/2022, Pergub 127/2019)
3. Identify gaps — what's missing for full compliance
4. Provide confidence score (0.0-1.0)
5. Respond in Indonesian

Uses the existing `_llm_json()` helper pattern from `document_tool_service.py`.

#### BJR Score Calculation

```python
def calculate_bjr_score(decision_id: str) -> float:
```

Calculates overall BJR completeness score (0-100) based on:
- Required checklist items with approved evidence / total required items per completed phase
- Weighted by phase (pre_decision: 30%, decision: 40%, post_decision: 30%)
- Items with `review_status = 'rejected'` count as incomplete

### Integration Points

**Approval workflow**: `submit-phase` creates an `approval_request` with:
- `resource_type = 'bjr_phase'`
- `resource_id = decision_id`
- `title = f"BJR Phase Review: {decision.title} — {phase_display_name}"`
- Template: uses existing workflow template or a BJR-specific one seeded at migration

**Required changes to `approvals.py`**:
1. In `get_approval_request` (line ~119): Add `elif request["resource_type"] == "bjr_phase"` to fetch the BJR decision as the resource (currently only fetches `document_tool_result`).
2. In `take_action` (line ~158): After the approval status update block, add a post-approval hook: if `request["resource_type"] == "bjr_phase"` and `body.action == "approve"` and this was the final step, call `bjr_advance_phase(request["resource_id"])` to move the decision to the next phase. Import from `bjr_service.py`.

**Audit trail**: All mutations call `log_action()` with `resource_type = 'bjr_decision'`.

**Obligations**: The BJR decision page includes a "Create Obligation" action that pre-fills `decision_id` context. Post-decision monitoring obligations naturally link back.

**Dashboard extension**: `dashboard.py` summary endpoint extended with BJR metrics, or consumed from `/bjr/summary`.

---

## Frontend Architecture

### Page 1: BJR Dashboard — `BJRDashboardPage.tsx`

**Route**: `/bjr`
**IconRail**: `ShieldCheck` icon, positioned after Dashboard

**Sidebar (340px)**:
- "Keputusan Baru" (New Decision) button
- Phase filter: Pre-Decision / Decision / Post-Decision / Completed
- Status filter: Draft / In Progress / Under Review / Approved
- Risk level filter
- GCG Compliance summary widget (11 aspects, mini progress indicators)

**Content area**:
- **Summary row**: 4 cards — Total Decisions, By Phase (mini bar), Open Risks, Average BJR Score
- **Decision list**: Cards showing title, phase badge (color-coded), status badge, risk level chip, BJR score progress bar (0-100%), date, decision type
- **Standing Risks panel**: Collapsible section showing 4 global risks with status and mitigation

### Page 2: BJR Decision Detail — `BJRDecisionPage.tsx`

**Route**: `/bjr/decisions/:id`

**Header section**:
- Decision title (editable in draft status)
- Type badge, risk level badge, estimated value
- BJR Score: large circular progress indicator (0-100%)
- Action buttons: "Submit Phase for Review" / "Cancel Decision"

**Phase stepper** (horizontal):
- 3 steps: Pre-Decision → Decision → Post-Decision
- Current phase highlighted, completed phases have checkmark
- Locked phases show lock icon
- Click to view any phase (read-only for completed/future phases)

**Checklist panel** (main content, for current/selected phase):
- Each checklist item as an expandable card:
  - Title + required badge
  - Regulatory references (clickable links to regulation details)
  - Evidence list (if any): title, type icon, LLM assessment badge (satisfies/gaps), confidence score
  - "Attach Evidence" button → modal with tabs:
    - **Upload File**: DropZone for direct file upload
    - **Link Tool Result**: Searchable list of user's compliance checks, analyses, etc.
    - **Manual Note**: Textarea for justification text
    - **External Link**: URL input
  - After attachment: "Assess Evidence" button triggers LLM evaluation
  - Status: green check (approved evidence), amber (pending review), red (rejected/gaps), gray (no evidence)

**Risk register panel** (collapsible):
- Decision-specific risks + linked global risks
- "Add Risk" button
- Status controls (open → mitigated → accepted → closed)

**Activity timeline** (collapsible):
- Audit trail entries for this decision (filtered from audit_logs)

### Admin Pages

**Regulatory Items Manager**: List + modal CRUD. Table view with layer filter tabs (UU / PP / Pergub / OJK-BEI / Custom). Follows `ClauseLibraryPage.tsx` pattern.

**Checklist Template Manager**: Grouped by phase. Drag-to-reorder within phase. Required/optional toggle.

**GCG Aspects Manager**: List with indicators and frequency. Simple CRUD.

All accessible from Admin Settings page as new sections.

### Navigation Changes

- **IconRail**: Add BJR as a **standalone item** (not inside a group flyout) using the `Scale` icon → `/bjr`. Position it between the Dashboard standalone item and the separator, since BJR is a primary workflow — not a sub-tool. The `standaloneItems` array in `IconRail.tsx` gets a third entry.
- **Nested route**: `/bjr/decisions/:id` is a child route under the AppLayout, same pattern as other pages.
- i18n: ~60 keys per locale (decision CRUD, phases, checklist, evidence, risks, GCG)

---

## Seed Data

### Regulatory Items (28 total)

**Layer 1 — UU (6)**:
1. UU No. 40/2007 — Perseroan Terbatas (BJR basis, Art. 97(5))
2. UU No. 23/2014 — Pemerintahan Daerah
3. UU No. 19/2003 — BUMN
4. UU No. 1/2025 — Perubahan UU BUMN (removes state finance classification)
5. UU No. 6/2023 — Cipta Kerja
6. UU No. 40/2007 jo. UU No. 6/2023 — Art. 97 & 104 (BJR full)

**Layer 2 — PP (3)**:
1. PP No. 54/2017 — BUMD (master regulation)
2. PP No. 23/2022 — BUMN governance (explicit BJR adoption, 3-phase framework)
3. PP No. 45/2005 — BUMN governance (predecessor)

**Layer 3 — Pergub/KepGub DKI (14)**:
1. KepGub 96/2004 — GCG mandate for DKI BUMDs
2. KepGub 4/2004 — BUMD health assessment
3. Pergub 109/2011 — BUMD organ structure
4. Pergub 10/2012 — RJPP (long-term planning)
5. Pergub 204/2016 — Procurement
6. Pergub 5/2018 — Director appointment
7. Pergub 50/2018 — Supervisory board
8. Pergub 79/2019 — Organ remuneration
9. Pergub 127/2019 — RKAB (business plan — critical for BJR validity)
10. Pergub 131/2019 — BUMD oversight
11. Pergub 1/2020 — Internal control system (SPI)
12. Pergub 13/2020 — Audit committee
13. Pergub 92/2020 — Investment management
14. SE Gubernur 13/2017 — LHKPN integrity

**Layer 4 — OJK & BEI (5)**:
1. POJK 21/2015 — GCG for public companies
2. POJK 34/2014 — Nomination & remuneration committee
3. POJK 35/2014 — Corporate secretary
4. Peraturan BEI No. I-A — IDX listing rules
5. POJK 29/2016 — Annual reporting

### Checklist Items (16 total)

**Pre-Decision (5)**:
1. Due diligence completed comprehensively (PP 23/2022, PP 54/2017)
2. Feasibility study documented (PP 23/2022, Pergub 127/2019)
3. Activity within approved RKAB (Pergub 127/2019)
4. Activity within RJPP (Pergub 10/2012)
5. No conflict of interest (UU PT Art. 97(5)c)

**Decision (6)**:
1. Board meeting with valid quorum (UU PT, Anggaran Dasar)
2. Minutes of Meeting signed (UU PT, POJK 21/2015)
3. Risk analysis in minutes (PP 23/2022, POJK 21/2015)
4. Legal review of contracts (PP 23/2022, Anggaran Dasar)
5. Supervisory board approval obtained (Pergub 50/2018, Anggaran Dasar)
6. OJK/BEI disclosure made if material (POJK 29/2016, Peraturan BEI)

**Post-Decision (5)**:
1. Monitoring & evaluation mechanism established (PP 23/2022, Pergub 131/2019)
2. Internal control system (SPI) active (Pergub 1/2020)
3. Audit committee informed (Pergub 13/2020, PP 54/2017)
4. Periodic reports to supervisory board (Pergub 50/2018, POJK 21/2015)
5. Complete documentation stored and accessible (UU PT Art. 97(5), PP 23/2022)

### GCG Aspects (11)

1. Tata Kelola Organ — PP 54/2017, Pergub 109/2011 — Annually/Monthly — Sekper/Legal
2. Rencana Bisnis — Pergub 127/2019, Pergub 10/2012 — Annually — Direksi/Keuangan
3. Pengadaan B/J — Pergub 204/2016, PP 54/2017 — Per transaction — Procurement
4. Investasi & Capex — Pergub 92/2020, PP 23/2022 — Per decision — BD/Keuangan
5. Laporan Keuangan — POJK 29/2016, UU PT — Quarterly/Annually — Keuangan/Sekper
6. Keterbukaan Informasi — POJK 21/2015, Peraturan BEI — Per material event — Sekper/Legal
7. Audit Internal — PP 54/2017, Pergub 1/2020 — Periodic — SPI/Komite Audit
8. Komite Audit — Pergub 13/2020, POJK 35/2014 — Monthly/Annually — Komite Audit
9. Remunerasi Organ — Pergub 79/2019, POJK 34/2014 — Annually — HR/Sekper
10. LHKPN & Integritas — SE Gub 13/2017 — Annually — Legal/HR
11. BJR Documentation — UU PT 97(5), PP 23/2022 — Per decision — Direksi/Legal/BD

### Standing Risks (4)

1. **Dualisme Rezim Hukum** [HIGH] — Ancol subject to corporate AND regional finance law simultaneously
2. **Keputusan di Luar RKAB** [HIGH] — Decisions outside approved RKAB void BJR protection
3. **Transisi Kepemimpinan** [MEDIUM] — Leadership gaps create decision legitimacy risks
4. **Disclosure Tidak Tepat Waktu** [MEDIUM] — Late OJK/BEI disclosure weakens GCG position

---

## Phase-Gate Approval Flow

```
Direksi creates decision (status: draft)
    ↓
Direksi fills PRE-DECISION checklist items + attaches evidence
    ↓
LLM assesses each evidence (confidence gating via HITL)
    ↓
Direksi clicks "Submit Phase for Review"
    → Creates approval_request (resource_type: 'bjr_phase', phase: 'pre_decision')
    → Decision status: 'under_review'
    ↓
Legal/Compliance reviews in approval inbox
    → Can view all evidence + LLM assessments
    → Approve: advances to DECISION phase
    → Reject: returns to Direksi with comments
    → Return: sends back for more evidence
    ↓
[Repeat for DECISION phase]
    ↓
[Repeat for POST-DECISION phase]
    ↓
All 3 phases approved → decision status: 'completed'
    → BJR protection fully documented
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `supabase/migrations/021_bjr_governance.sql` | 6 tables + RLS + indexes + triggers + seed data |
| `backend/app/routers/bjr.py` | All BJR endpoints (~300 lines) |
| `backend/app/services/bjr_service.py` | LLM evidence assessment + score calculation (~120 lines) |
| `backend/app/models/bjr.py` | Pydantic request/response models (~80 lines) |
| `frontend/src/pages/BJRDashboardPage.tsx` | Decision overview + GCG summary (~400 lines) |
| `frontend/src/pages/BJRDecisionPage.tsx` | Decision lifecycle detail (~500 lines) |
| `frontend/src/components/bjr/PhaseProgress.tsx` | Phase stepper component (~60 lines) |
| `frontend/src/components/bjr/ChecklistItem.tsx` | Evidence-attachable checklist item (~120 lines) |
| `frontend/src/components/bjr/EvidenceAttachModal.tsx` | Modal for attaching evidence (~150 lines) |
| `frontend/src/components/bjr/RiskCard.tsx` | Risk register card (~50 lines) |

## Files to Modify

| File | Change | Lines Affected |
|------|--------|----------------|
| `backend/app/main.py` | Import + register `bjr.router` (line 5 import, line ~52 include_router) | ~2 lines |
| `backend/app/routers/approvals.py` | (1) `get_approval_request`: add `elif` for `bjr_phase` resource fetch (~line 119). (2) `take_action`: add post-approval hook to call `bjr_advance_phase()` when `resource_type='bjr_phase'` is approved (~line 168). | ~15 lines |
| `backend/app/routers/dashboard.py` | Add BJR summary query (decisions by phase, open risks count) to `/summary` endpoint | ~20 lines |
| `frontend/src/App.tsx` | Import BJR pages, add `<Route path="bjr" ...>` and `<Route path="bjr/decisions/:id" ...>` inside AppLayout | ~5 lines |
| `frontend/src/components/layout/IconRail.tsx` | Add `{ path: '/bjr', icon: Scale, labelKey: 'nav.bjr' }` to `standaloneItems` array (line 26-28) | ~1 line |
| `frontend/src/lib/translations.ts` | Add ~60 BJR i18n keys per locale (nav, decision CRUD, phases, checklist, evidence, risks, GCG) | ~120 lines |
| `frontend/src/pages/AdminSettingsPage.tsx` | Add BJR admin sections (regulatory items, checklist templates, GCG aspects management) | ~100 lines |

---

## Estimated Scope

- **New code**: ~2,800-3,500 lines
- **Modified code**: ~200-300 lines across 7 existing files
- **New tables**: 6
- **New migration**: 1 (with extensive seed data)
- **New routes**: ~25 API endpoints
- **New pages**: 2 main + admin sections
- **New components**: 4 BJR-specific

This is comparable in scope to Phase 1's 7 features combined, but structured as a single cohesive module. It represents LexCore's transition from a document analysis tool to a **decision governance platform**.

---

## Verification Plan

### Backend
1. Import check: `python -c "from app.main import app; print('OK')"`
2. Migration: Apply `021_bjr_governance.sql` to Supabase, verify 6 tables created with seed data
3. API tests: Create `tests/api/test_bjr.py` covering:
   - BJR-01: Create decision
   - BJR-02: List decisions with filters
   - BJR-03: Attach evidence (file upload + tool result reference)
   - BJR-04: LLM evidence assessment (confidence scoring)
   - BJR-05: Submit phase for approval
   - BJR-06: Phase advancement on approval
   - BJR-07: BJR score calculation
   - BJR-08: Risk register CRUD
   - BJR-09: Admin CRUD (regulatory items, checklist templates, GCG aspects)
   - BJR-10: RLS enforcement (users only see own decisions)

### Frontend
1. TypeScript: `npx tsc --noEmit` clean
2. Lint: `npm run lint` clean
3. Visual QA: Navigate all BJR pages in both light and dark themes
4. i18n: Verify Indonesian and English translations render correctly

### Integration
1. End-to-end: Create decision → attach evidence (link existing compliance check result) → LLM assessment → submit phase → approve in inbox → advance → complete all 3 phases
2. Dashboard: BJR metrics appear in executive dashboard
3. Audit trail: All BJR actions visible in audit log

### Production
1. Deploy backend to Railway
2. Deploy frontend to Vercel
3. Smoke test on production URL
