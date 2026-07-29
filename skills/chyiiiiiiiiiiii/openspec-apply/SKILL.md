---
name: openspec-apply
description: Implement a change proposal following the OpenSpec SDD workflow. Use after a proposal is approved and ready for implementation.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# OpenSpec: Apply

Implement a change proposal following the OpenSpec SDD workflow.

## Usage

```
/openspec-apply <change-id>
```

**Example:**
```
/openspec-apply add-user-search
```

## What This Skill Does

1. Read the proposal and understand the scope
2. Follow tasks.md step by step
3. Implement according to delta specs
4. Mark tasks complete as you progress
5. Run quality gates after each phase

## Execution Steps

### Step 1: Load Context

Read these files in order:

1. `openspec/project.md` - Project conventions
2. `openspec/changes/{change-id}/proposal.md` - What and why
3. `openspec/changes/{change-id}/tasks.md` - Implementation checklist
4. `openspec/changes/{change-id}/specs/*.md` - Delta specifications

### Step 2: Verify Prerequisites

Before starting:

```bash
git status          # Should be clean or on feature branch
# Run project's lint/analyze command
```

If not on a feature branch:
```bash
git checkout -b feature/{change-id}
```

### Step 3: Execute Tasks Phase by Phase

For each phase in tasks.md:

#### 3.1 Start Phase
- Mark the first task as in-progress in your todo list
- Read the delta spec for that component

#### 3.2 Implement Task
- Follow existing patterns from project's CLAUDE.md
- Write code according to delta spec requirements
- Include tests for new functionality

#### 3.3 Mark Complete
- Update tasks.md: `- [ ]` → `- [x]`
- Add completion note if significant

#### 3.4 Quality Gate
After completing each phase, run project quality checks:
```bash
# Example for Flutter projects:
# make format && make analyze && make run_unit_test

# Example for Node projects:
# npm run lint && npm test
```

### Step 4: Update Progress

After each phase, update `tasks.md`:

```markdown
## Phase 1: Foundation (Data Layer)

- [x] 1.1 Create search model ✓ 2024-01-15
- [x] 1.2 Add search to repository ✓ 2024-01-15
- [x] 1.3 Write unit tests ✓ 2024-01-15

**Quality Gate:** PASSED
```

### Step 5: Handle Issues

If you encounter blockers:

1. Document in tasks.md under the task
2. Add a `### Blockers` section if needed
3. Ask for clarification before proceeding

```markdown
- [ ] 1.2 Add search to repository
  - **Blocker:** Unclear if fuzzy search should use DB or in-memory
  - **Options:** A) Database query, B) In-memory filtering
  - **Waiting for:** Decision from user
```

### Step 6: Completion Check

When all tasks are done:

1. Verify all checkboxes are `[x]`
2. Run full quality gate
3. Update proposal.md status:
   ```markdown
   **Status:** Implementation Complete
   **Completed:** {YYYY-MM-DD}
   ```

### Step 7: Report Completion

```markdown
## Implementation Complete: {change-id}

### Summary
- {Brief description of what was implemented}

### Files Changed
- `lib/feature/...` - {description}
- `test/...` - {description}

### Quality Verification
- [x] All tests passing
- [x] Lint/analyze clean
- [x] Documentation updated (if applicable)

### Next Step
Run `/openspec-archive {change-id}` to complete the workflow.
```

## Implementation Rules

### Follow Project Conventions
- Read and follow project's CLAUDE.md
- Use existing patterns and styles
- Match naming conventions

### Maintain Quality
- Write tests as you implement
- Handle errors properly with specific exception types
- Keep code clean and readable

### Stay in Scope
- Only implement what's in the delta spec
- Don't add "nice to have" features
- Flag scope questions before proceeding

### Document Changes
- Update relevant documentation
- Sync localization files if adding strings
- Update project docs if introducing new patterns
