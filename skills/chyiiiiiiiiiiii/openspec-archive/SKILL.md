---
name: openspec-archive
description: Complete a change and update the source of truth specifications. Use after all implementation tasks are finished and verified.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# OpenSpec: Archive

Complete a change and update the source of truth specifications.

## Usage

```
/openspec-archive <change-id>
```

**Example:**
```
/openspec-archive add-user-search
```

## What This Skill Does

1. Verify all tasks are complete
2. Merge delta specs into main specs
3. Move change to archive with timestamp
4. Update completion status

## Execution Steps

### Step 1: Verify Completion

Check `openspec/changes/{change-id}/tasks.md`:

- [ ] All tasks marked `[x]`
- [ ] All quality gates passed
- [ ] No open blockers

If incomplete, report what's missing and stop.

### Step 2: Final Quality Check

Run project's quality verification commands. All must pass before archiving.

### Step 3: Merge Delta Specs

For each file in `openspec/changes/{change-id}/specs/`:

#### 3.1 Check if target spec exists

- If `openspec/specs/{component}.md` exists → Merge changes
- If not → Create new spec file

#### 3.2 Apply ADDED sections

Copy new requirements to the target spec:

```markdown
# {Component} Specification

## Requirements

### {New Requirement from Delta}
{Description}

#### Scenario: {Name}
- GIVEN ...
- WHEN ...
- THEN ...
```

#### 3.3 Apply MODIFIED sections

Update existing requirements in target spec with new content.

#### 3.4 Apply REMOVED sections

Remove deprecated requirements from target spec.
Add to a `## Deprecated` section for reference:

```markdown
## Deprecated

### {Removed Requirement} (Removed: {date})
Reason: {from delta spec}
```

### Step 4: Archive the Change

```bash
# Create archive directory with timestamp
mkdir -p openspec/archive/{change-id}

# Move all change files
mv openspec/changes/{change-id}/* openspec/archive/{change-id}/
rmdir openspec/changes/{change-id}
```

### Step 5: Update Archive Metadata

Add completion info to `openspec/archive/{change-id}/proposal.md`:

```markdown
---

## Archive Information

**Archived:** {YYYY-MM-DD HH:MM}
**Duration:** {days from creation to archive}
**Outcome:** Successfully implemented

### Files Modified
- `lib/feature/...`
- `test/...`

### Specs Updated
- `openspec/specs/{component}.md`
```

### Step 6: Commit the Archive

```bash
git add openspec/
git commit -m "docs(openspec): archive {change-id}

- Merged delta specs into main specs
- Archived change history
- Implementation complete"
```

### Step 7: Report Completion

```markdown
## Archived: {change-id}

### Specs Updated
- `openspec/specs/{component}.md` - {summary of changes}

### Archive Location
- `openspec/archive/{change-id}/`

### Change History
- Created: {original date}
- Completed: {today}
- Duration: {X days}

### Summary
{Brief description of what was accomplished}

---

The OpenSpec workflow for this change is complete.
The specifications are now the source of truth.
```

## Merge Strategy

### For ADDED content
- Append to existing spec under appropriate section
- Maintain consistent formatting
- Add creation date comment if helpful

### For MODIFIED content
- Replace the existing requirement
- Keep the same location in the document
- Note the modification date

### For REMOVED content
- Move to Deprecated section (don't delete immediately)
- Include removal reason and date
- Can be fully removed in future cleanup

## Troubleshooting

### Tasks not complete
```
Cannot archive: {X} tasks still pending in tasks.md.
Please complete all tasks first or update tasks.md if they're done.
```

### Quality gate fails
```
Cannot archive: Quality checks failed.
Please fix issues before archiving.
```

### Merge conflict in specs
If the target spec has changed since the proposal:
1. Review both versions
2. Manually resolve conflicts
3. Ensure final spec is consistent
4. Proceed with archive
