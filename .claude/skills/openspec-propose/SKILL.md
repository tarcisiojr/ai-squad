---
name: openspec-propose
description: Use when creating a new feature proposal. Creates proposal.md, specs/, design.md and tasks.md in one step. Trigger on /opsx:propose or when user wants to propose, plan or spec a new change.
---

# OpenSpec Propose

Creates a complete change proposal with all planning artifacts in one step.

## Steps

1. Run `openspec new change $ARGUMENTS --json` to scaffold the change
2. Run `openspec ff --change $ARGUMENTS --json` to generate all artifacts

## Artifacts produced

- proposal.md — why and what
- specs/ — requirements and scenarios  
- design.md — technical approach
- tasks.md — implementation checklist

After artifacts are ready, use /opsx:apply to implement.
