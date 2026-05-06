# wx Profile Presence Overlay

This directory is a sanitized repository copy of the wx proactive presence system.

Runtime deployment path on the VPS:

```text
/home/hermes/.hermes/profiles/wx
```

Tracked here:

- `presence/kernel/`: generic Proactive Presence Kernel
- `presence/profiles/linjiang/`: first profile configuration instance
- `presence/schemas/`: JSON schemas
- `conversation/schemas/`: sanitized ledger schema
- `scripts/`: cron wrapper entry points
- `cron/jobs.presence.example.json`: example Hermes cron job
- `config.yaml.example`: sanitized Hermes wx profile config
- `linjiang-llm.env.example`: sanitized legacy/proxy LLM env example

Not tracked:

- API keys and `.env` files
- WeChat auth files
- conversation ledgers, sessions, runtime state, events, backups, caches, logs, and databases

To deploy from this overlay, copy the relevant files into the runtime profile and then fill local secret values from a private env/config source.
