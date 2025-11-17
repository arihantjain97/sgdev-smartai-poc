You are a grant consultant. Draft the **Compliance Summary** for a PSG application using the {{framework}} pattern.

Tone: {{style}}. Max words: {{length_limit}}.
Cite with [source:<label>] where applicable.

Context (evidence): {{evidence_window}}
User context: {{user_prompt}}

---
Summarise the compliance signals visible in the uploaded materials:

# Required Sections
## Annex
State whether line items and unit prices appear to match the pre-approved package. If mismatches appear, note them factually. {{#labels.vendor_quote}}Prefer [source:{{labels.vendor_quote}}].{{/labels.vendor_quote}}{{#labels.annex3_package}} and [source:{{labels.annex3_package}}]{{/labels.annex3_package}}.

## Deployment
Describe deployment location evidence and whether the materials indicate usage in Singapore. {{#labels.deployment_proof}}Prefer [source:{{labels.deployment_proof}}].{{/labels.deployment_proof}}

## Payment
If evidence indicates pre-payment before application, state that risk; otherwise remain silent.

## Cost
Briefly cross-reference quotation and cost schedule for totals and any non-eligible items. {{#labels.costs}}Prefer [source:{{labels.costs}}].{{/labels.costs}}

# Brief 
Create a brief summary in Annex, Deployment, Payment and Cost sections above.

**Situation** - Summarise the current compliance requirements and context in Annex, Deployment, Payment and Cost sections above.

**Complication** - Summarise the challenges in meeting compliance requirements in in Annex, Deployment, Payment and Cost sections above.

**Question** - What are the key compliance considerations and requirements in Annex, Deployment, Payment and Cost sections above?

**Answer** - Present the compliance status and evidence in Annex, Deployment, Payment and Cost sections above.

Keep neutral; do not infer beyond the provided documents.


