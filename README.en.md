<div align="center">

[中文](README.md) | [English](README.en.md)

</div>

# agent-duet

> A duet between you and your agent — turning the waterfall into a scored, multi-voice piece.

agent-duet is a **local, self-hosted agent workspace**: it presents an agent's
thinking, tool calls, and final replies in a structured, separated way — and keeps
a dossier for every session and a record for every authorization.

![Session view](docs/images/session.png)

## What it solves

| Pain point | agent-duet's answer |
|---|---|
| Long sessions — forget which directory they were in | Every session gets a dossier: directory + topic + status, searchable |
| Terminal waterfall = low information density | Multi-voice view: melody (reply) / murmur (thinking) / action (tools) separated |
| Different modes presented identically | Mode-aware: in guided mode every write prompts an authorization card, with approve/deny/timeout permanently recorded |
| Fragmented across agents | Profile system: adding a new agent = one profile + one adapter |

## Quick start

```bash
# backend
cd backend && uv sync && uv run uvicorn app.main:app --port 8300

# frontend
cd frontend && npm install && npm run dev
```

Open **http://localhost:5173**. See [Getting started](docs/getting-started.md).

## Interface

![Home](docs/images/home.png)

Three-column layout:

- **Left**: session list (search by title, grouped by directory, current session highlighted)
- **Center**: the conversation — your prompt, the backstage work (collapsed), the final reply (paper card)
- **Right**: session context — mode switcher, basic info, Git status, playbill (Requests)

## Core concepts

- **Duet / three voices**: an agent's output has three layers — what it says to you
  (melody), what it thinks to itself (murmur), what it does (action). agent-duet keeps them apart.
- **Raw-first**: every turn's raw event stream is saved (`data/raw/`); derived data is
  computed on read, so any future need can be satisfied by replay.
- **Authorization as data**: every approve/deny/timeout is a structured record,
  attached to its tool call.
- **Transaction status vs interaction outcome**: completed / incomplete / failed /
  terminated describe the task; approved / denied / timed out describe each authorization. Orthogonal.

## Vision

The ultimate consumer of structured session data isn't just you — it's the agent itself.
Through offline "meditation" over its own thinking chains and failures, an agent distills
and maintains its own working norms — moving from being constrained to self-constraining.

## Docs

- [Getting started](docs/getting-started.md)
- [FAQ](docs/faq.md)
- [Devlog](docs/devlog/)

## Tech stack

Python + FastAPI · SQLite · claude-agent-sdk · Vue 3 + Vite

## License

(TODO: add your license)
