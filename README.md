# ai-spend-pipeline

The pipelines behind Kestrel Motor Manufacturing's executive **AI Spend**
report: usage and billing data from every AI tool the company pays for,
landed nightly, cleaned, and turned into the tables leadership reads.

Kestrel is a fictional company. All data here is generated.

```
ingest/           one Python module per source; loads a landed day into raw
dbt/              staging and marts models, with tests and column descriptions
docs/runbook.md   how loads work, how to reload a day, who to tell
.github/workflows nightly.yml (load + build), ci.yml (every pull request)
```

Start with [`docs/runbook.md`](docs/runbook.md).
