# /opsx:propose

Creates a complete change proposal with all planning artifacts in one step.

## Usage

/opsx:propose <change-name>

## Steps

1. Run `openspec new change $ARGUMENTS --json`
2. Run `openspec ff --change $ARGUMENTS --json`

## Artifacts produced

- proposal.md — why and what
- specs/ — requirements and scenarios
- design.md — technical approach
- tasks.md — implementation checklist

After artifacts are ready, use /opsx:apply to implement.
