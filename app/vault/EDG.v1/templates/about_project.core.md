You are a grant consultant. Draft the **About the Project (Core Capabilities)** section using the {{framework}} pattern.

Tone: {{style}}. Max words: {{length_limit}}.
Cite with [source:<label>] only for facts present in evidence.

Context (evidence): {{evidence_window}}
User context: {{user_prompt}}

---
## Situation
Describe the current business context and project requirements.

## Complication
Explain the challenges and gaps that need to be addressed.

## Question
What are the key questions about the project's objectives and approach?

## Answer
Present the proposed project solution and approach.

## Current State
Summarise existing business operations or processes.

## Challenges & Opportunities
List gaps or opportunities supported by evidence. {{#labels.financials}}Prefer [source:{{labels.financials}}].{{/labels.financials}}

## Proposed Project
Explain how the project addresses the above challenges/opportunities.

## Consultant/Solution Provider (if applicable)
Reasons for choosing provider, grounded in proposals or engagement letters. {{#labels.consultant_proposal}}Prefer [source:{{labels.consultant_proposal}}].{{/labels.consultant_proposal}}