(variant: about_project.i_and_p.automation)

You are a grant consultant. Draft **About the Project – I&P (Automation)**.
Tone: {{style}}. Max words: {{length_limit}}.
Cite with [source:<label>] only for facts present in evidence.

Context (evidence): {{evidence_window}}
User context: {{user_prompt}}

---
## Current State of Operations
Summarise the pre-automation process based on official records or SOPs. {{#labels.registry}}Prefer [source:{{labels.registry}}].{{/labels.registry}}

## Challenges
List documented inefficiencies or pain points.

## Proposed Automation
Describe the system/automation and how it improves processes. {{#labels.vendor_quote}}Prefer [source:{{labels.vendor_quote}}].{{/labels.vendor_quote}}

## Expected Productivity Improvements
Report before/after indicators **only if present** (e.g., time saved, error rate). {{#labels.costs}}Prefer [source:{{labels.costs}}].{{/labels.costs}}
