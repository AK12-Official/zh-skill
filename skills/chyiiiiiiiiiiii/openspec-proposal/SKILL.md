---
name: openspec-proposal
description: Create a new change proposal following the OpenSpec SDD workflow. Use when starting a new feature, enhancement, or significant change that needs specification tracking.
allowed-tools: Read, Write, Glob, Grep, Bash
---

# OpenSpec: Proposal

Create a new change proposal following the OpenSpec Spec-Driven Development workflow.

## Usage

```
/openspec-proposal <feature description>
```

**Example:**
```
/openspec-proposal add user search feature
```

## What This Skill Does

1. Generate a unique change ID from the description (kebab-case)
2. Create the change directory structure under `openspec/changes/`
3. Generate proposal.md, tasks.md, and delta specs
4. Present the proposal for review

## Execution Steps

### Step 1: Generate Change ID

Convert the description to kebab-case for the change ID.

**Example:** "add user search" → `add-user-search`

### Step 2: Create Directory Structure

```bash
mkdir -p openspec/changes/{change-id}/specs
```

### Step 3: Generate proposal.md

Create `openspec/changes/{change-id}/proposal.md`:

```markdown
# Proposal: {Feature Title}

**Change ID:** `{change-id}`
**Created:** {YYYY-MM-DD}
**Status:** Draft

---

## Problem Statement

{Analyze the request and describe:}
- What problem are we solving?
- Who is affected?
- What's the current pain point?

## Proposed Solution

{High-level approach:}
- Key components
- Technical approach
- Expected outcomes

## Scope

### In Scope
- {Core functionality}
- {Essential features}

### Out of Scope
- {Explicitly excluded items}
- {Future considerations}

## Impact Analysis

| Component | Change Required | Details |
|-----------|-----------------|---------|
| Database | Yes/No | {details} |
| API | Yes/No | {details} |
| State | Yes/No | {details} |
| UI | Yes/No | {details} |

## Architecture Considerations

{How does this fit with existing patterns?}
{Any new patterns introduced?}
{Dependencies on other components?}

## Success Criteria

- [ ] {Measurable outcome 1}
- [ ] {Measurable outcome 2}
- [ ] {Measurable outcome 3}

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| {risk} | Low/Med/High | Low/Med/High | {strategy} |
```

### Step 4: Generate tasks.md

Create `openspec/changes/{change-id}/tasks.md`:

```markdown
# Implementation Tasks: {Feature Title}

**Change ID:** `{change-id}`

---

## Phase 1: Foundation (Data Layer)

- [ ] 1.1 {Data model task}
- [ ] 1.2 {Repository task}
- [ ] 1.3 {Data layer tests}

**Quality Gate:**
- [ ] Code analysis passes
- [ ] Unit tests pass

---

## Phase 2: Business Logic (Domain/State)

- [ ] 2.1 {Provider/state task}
- [ ] 2.2 {Business logic task}
- [ ] 2.3 {Provider tests}

**Quality Gate:**
- [ ] Code analysis passes
- [ ] State transitions tested

---

## Phase 3: User Interface

- [ ] 3.1 {Page/widget task}
- [ ] 3.2 {Component task}
- [ ] 3.3 {Widget tests}

**Quality Gate:**
- [ ] Code analysis passes
- [ ] Widget tests pass

---

## Phase 4: Integration & Polish

- [ ] 4.1 Add i18n strings (if applicable)
- [ ] 4.2 Integration testing
- [ ] 4.3 Performance verification
- [ ] 4.4 Documentation update

**Quality Gate:**
- [ ] All tests pass
- [ ] Code analysis clean
- [ ] Documentation synced

---

## Completion Checklist

- [ ] All phases complete
- [ ] All quality gates passed
- [ ] Documentation synced
- [ ] Ready for `/openspec-archive`
```

### Step 5: Generate Delta Spec

Create `openspec/changes/{change-id}/specs/{component}_delta.md`:

```markdown
# Delta: {Component Name}

**Change ID:** `{change-id}`
**Affects:** {list of affected areas}

---

## ADDED

### Requirement: {New Requirement Title}

{Description of new functionality}

#### Scenario: {Scenario Name}
- GIVEN {precondition}
- WHEN {action}
- THEN {expected result}

---

## MODIFIED

### Requirement: {Existing Requirement Title}

{Updated description}

#### Scenario: {Updated Scenario}
- GIVEN {new precondition}
- WHEN {new action}
- THEN {new result}

---

## REMOVED

{List any deprecated requirements, or "(None)" if nothing removed}
```

### Step 6: Present for Review

After generating all files, summarize:

```
## Proposal Created: {change-id}

### Files Generated:
- `openspec/changes/{change-id}/proposal.md`
- `openspec/changes/{change-id}/tasks.md`
- `openspec/changes/{change-id}/specs/{component}_delta.md`

### Next Steps:
1. Review the proposal.md for accuracy
2. Adjust tasks.md if needed
3. Verify delta specs match requirements
4. When ready: `/openspec-apply {change-id}`
```

## Important Notes

- Read existing specs in `openspec/specs/` to understand current state
- Reference `openspec/project.md` for project conventions
- Align with patterns in project's CLAUDE.md
- Keep scope minimal - avoid feature creep
