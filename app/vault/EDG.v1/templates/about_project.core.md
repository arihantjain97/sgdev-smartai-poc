You are a grant consultant. Draft the **About the Project (Core Capabilities)** section.
Tone: {{style}}. Max words: {{length_limit}}.
Cite with [source:<label>] only for facts present in evidence.

Context (evidence): {{evidence_window}}
User context: {{user_prompt}}

---
## Current State
Summarise existing business operations or processes.

## Challenges & Opportunities
List gaps or opportunities supported by evidence. {{#labels.financials}}Prefer [source:{{labels.financials}}].{{/labels.financials}}

## Proposed Project
Explain how the project addresses the above challenges/opportunities.

## Consultant/Solution Provider (if applicable)
Reasons for choosing provider, grounded in proposals or engagement letters. {{#labels.consultant_proposal}}Prefer [source:{{labels.consultant_proposal}}].{{/labels.consultant_proposal}}