# Add System Architecture Document

## Summary
Added a comprehensive System Architecture Document to the `docs/` directory to guide development and stakeholder understanding.

## Context / Problem
The project lacked a centralized architectural overview, making it difficult for new developers and stakeholders to understand the system's structure, components, and strategic alignment.

## What Changed
*   Created `docs/SYSTEM_ARCHITECTURE.md`:
    *   Executive Summary & Strategic Alignment
    *   C4 Model Diagrams (Context, Container, Component)
    *   Data Flow description
    *   Deployment & Cross-cutting concerns
    *   Risk assessment (specifically highlighting the Chunk Boundary Effect)

## How to Test
1.  Verify the file exists: `ls -l docs/SYSTEM_ARCHITECTURE.md`
2.  Review the content for accuracy against the codebase.

## Risk / Rollback Notes
*   **Risk:** None (Documentation only).
*   **Rollback:** Delete `docs/SYSTEM_ARCHITECTURE.md`.
