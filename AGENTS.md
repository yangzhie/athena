# Athena — AI-Powered Adaptive Learning

## Overview

Athena is an AI-powered adaptive learning application designed to help users learn any topic deeply and efficiently. Instead of acting as a traditional chatbot that simply answers questions, Athena proactively guides users through a personalised learning journey by continuously assessing their understanding, identifying knowledge gaps, and delivering targeted learning materials.

Athena is organised around university **units** (e.g. CSE5DMI Data Mining). A lecturer creates a study space for each offering of a unit and uploads its material: documents, lecture slides, sample exams and recordings. Each enrolled student learns inside that unit, with the unit's material as the source of truth. The adaptive learning loop below runs within a unit.

## Units, Study Spaces and Environments

Use these terms exactly, in code and in conversation:

- **Unit:** a subject, stable across years (e.g. CSE5DMI Data Mining).
- **Offering:** one run of a unit (year + semester). The lecturer's **study space** for it holds the course material and lectures.
- **Environment:** one student's private area inside one offering: their chat, quiz answers, sandboxes and notes.
- **Topic / Concept:** a topic is a teachable part of an offering; a concept is a cross-unit idea that topics map to (e.g. overfitting), so learning in one unit can build on another.
- **Learner profile:** the student-owned, cross-unit record of concepts studied, mastery and short learning notes.
- **Lecture clip:** a topic-labelled time range in a lecture recording, produced by lecture indexing and approved by the lecturer.

Roles: **lecturers** create study spaces, upload material, approve lecture clips and enrol students. **Students** learn in their own environment in each unit they are enrolled in.

## Privacy (hard requirements)

Students must trust that they can ask honest questions. In every feature, endpoint and query:

1. An environment belongs to exactly one (student, offering) pair, and only that student can read it.
2. Chats, individual quiz answers and memory notes never reach any lecturer-facing view or API.
3. Lecturers see class-level aggregates by default; individual insight only with the student's opt-in for that offering, which they can withdraw.
4. A lecturer of one unit never sees anything from the student's other units, even in aggregate.
5. Learner identity comes from trusted authentication on the server, never from client-supplied data.

## Core Learning Experience

Athena operates through an iterative adaptive learning loop:

1. **Diagnose:** Ask multiple-choice or open-ended questions to assess the user's existing knowledge, understanding, and misconceptions.
2. **Teach:** Provide concise, engaging, and interactive learning materials targeting concepts the user has not yet mastered.
3. **Reinforce:** Ask follow-up questions to evaluate understanding and strengthen knowledge retention.
4. **Adapt:** Adjust the difficulty, depth, and direction of learning based on the user's responses.
5. **Progress:** Continue towards more advanced concepts once prerequisite knowledge is demonstrated.

Users can respond through text, multiple-choice selections, or voice. Athena should proactively initiate questions rather than requiring users to formulate specific questions themselves.

## Adaptive Learning Scope

Athena dynamically adjusts the learning journey based on the complexity of the requested topic:

- **Small topics (e.g., Bubble Sort):** Conduct a short learning loop focused on the concept, resolving misconceptions and finishing once sufficient understanding is demonstrated.
- **Broad topics (e.g., Machine Learning):** Assess the user's current level, identify prerequisite knowledge gaps, and progressively guide them from foundational concepts towards advanced topics through multiple learning loops.

Learning should be mastery-driven rather than following a fixed sequence of lessons.

## Learning Content & Experience

Each learning iteration should deliver a **small, focused piece of content**, rather than overwhelming the learner with lengthy explanations or large amounts of information.

- **Microlearning:** Break complex concepts into small, digestible learning units, each addressing a specific knowledge gap.
- **Engaging Content:** Prioritise captivating and intuitive learning experiences using visual explanations, diagrams, animations, interactive widgets, simulations, and practical examples where appropriate.
- **Active Interaction:** Encourage learners to interact with materials rather than passively reading long blocks of text.
- **Visible Progress:** Make incremental improvements apparent through immediate feedback, concept mastery indicators, and progressively more challenging questions.
- **Adaptive Pacing:** Introduce new information gradually, allowing learners to demonstrate understanding before progressing. Avoid unnecessary repetition of concepts already mastered.

The goal is to make learning feel like a continuous series of small discoveries and achievements, rather than reading a conventional textbook.

## Key Principles

- **Active Learning:** Prioritise questioning, reasoning, active recall, and knowledge application over passive reading.
- **Personalisation:** Continuously adapt explanations, questions, and learning paths to each user's demonstrated understanding.
- **Source Grounding:** Use the unit's material as the authoritative source. Show references (document page or lecture timestamp) on answers, and say clearly when the material doesn't cover something and an answer is general knowledge.
- **Interactive Learning:** Support diverse learning formats, including explanations, quizzes, examples, visualisations, and relevant lecture video segments.
- **Knowledge Tracking:** Track mastered concepts, knowledge gaps, and learning progress to guide future interactions.
- **Extensibility:** Build each capability (tutor, quizzes, lecture clips, sandboxes, lecturer insights) so it can be developed on its own branch and plugged in without reworking the rest. A standalone "learn any topic" mode outside a unit is possible later but is not the current focus.

## Core Vision

Athena should not simply provide information. It should understand what the learner knows, discover what they do not understand, and guide them towards genuine mastery through continuous, engaging, and personalised learning interactions.

## Current App Structure

A single page:

- **Left sidebar:** the units the student is enrolled in (hardcoded in the proof of concept: CSE5DMI Data Mining and CSE5ALG Data Structures and Algorithms), a switch between the open unit's chat and its lecture clips, and a lecturer button to create a study space.
- **Main area:** the open unit's tutor chat (replies above, prompt box at the bottom, sources under each reply), or its lecture clips grouped by week.
- **Right side panel:** one item opened from the chat or clips: a lecture clip, a cited source passage, or an interactive sandbox.

## Repository

- `apps/web/`: React + TypeScript + Vite + Tailwind frontend. Runs on mock data.
  - Each feature lives in `src/features/<name>/` and registers itself in `src/app/features.ts`.
  - Pages only call `src/api/`, which returns mocks today. Swap those function bodies for real API calls and keep their signatures.
  - New side panel content is a new kind in `src/features/unit/panel/types.ts` plus a renderer in `renderers.ts`.
- `agent/`: Python adaptive learning agent (FastAPI, Pydantic, uv, pytest). See `agent/README.md`.
- `apps/api/`, `workers/`, `packages/shared/`, `infra/`, `docs/`: planned, placeholders only.

Commits follow Conventional Commits (`feat:`, `fix:`, `chore:`, `refactor:`, `style:`, `docs:`). Never commit `.env` files, API keys, or course material and lecture recordings.

**Open:** the agent's sessions are organised by learning goal, not by unit. How a unit maps to agent sessions (for example one session per unit, with the unit's material supplied as `materials`) is not yet decided.
