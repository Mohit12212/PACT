# Product specification — PACT

## Mission
Enable cross-sector collaboration in support of UN Sustainable Development Goal 17 by making capabilities visible, partnership delivery manageable, and reported outcomes more transparent.

## Primary users
- NGOs and community organisations with local needs, field access or volunteers.
- Colleges and research groups offering students, research capability and labs.
- Startups and companies offering technology, services, expertise or funding.
- Public-sector organisations coordinating programmes and service delivery.
- Platform administrators responsible for organisation verification and abuse response.

## Core journeys

### 1. Join the network
A representative registers an organisation, creates a profile, selects SDG focus areas, and publishes a need or offer. The profile should be specific enough to support meaningful discovery.

### 2. Find complementary partners
The matching service compares open needs and offers and returns ranked partner candidates. Users can inspect the match components, read an explanation, draft an introduction, and propose a collaboration.

### 3. Coordinate delivery
A proposal moves through proposed → negotiating → active → completed (or declined where allowed). Both organisations can communicate, create milestones, record completion, add outcome metrics and review completed work.

### 4. Report outcomes
The impact view aggregates metrics by SDG and supports CSV export and an AI-assisted narrative. User-entered metrics are not independently verified; the interface and documentation explicitly state that limitation.

### 5. Govern the network
Administrators review verification requests, manage account access and inspect the audit trail.

## Product principles
- **Action over vanity metrics:** prioritise next steps and delivery progress.
- **Explainability:** expose why a match was suggested and the component signals.
- **Human confirmation:** AI output is a draft; users control proposals and published claims.
- **Privacy-aware defaults:** local models are supported; do not send confidential personal data to an external provider without approval.
- **Impact integrity:** distinguish activities, outputs and outcomes; do not imply independent verification when none exists.
- **Progressive disclosure:** start with the next action, then expose detail when needed.

## Current scope
Working foundations include registration/login, organisation profiles, listings, partner matching, proposal lifecycle, milestones, messaging, impact metric entry, reviews, notifications, analytics, CSV export, optional AI features, admin verification and an audit log.

## Not yet production-complete
The current project now supports evidence URLs and an administrator review status for impact metrics, but does not independently authenticate sources. It does not provide robust identity verification, password recovery, MFA, formal data retention controls, managed multi-worker real-time infrastructure or a complete automated browser test suite. These are explicit roadmap items, not features to claim as complete.

## Match evaluation plan
Create a reviewed dataset of at least 100 realistic need/offer pairs across organisation types and SDGs. Have two reviewers label relevance on a 0–3 rubric. Report precision@3, precision@5, recall@5 and inter-rater agreement. Compare the current weighted score against keyword-only and random baselines. Record false positives, false negatives and subgroup performance by organisation type and SDG. Do not describe heuristic weights as validated until this evaluation has been completed.
