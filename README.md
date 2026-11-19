# Elderly Cloud Phone Agent

An autonomous AI agent designed to help seniors navigate mobile apps via voice commands on a cloud-based virtual smartphone.

## Architecture & Tech Stack
- **Voice Input**: Whisper (ASR) for speech-to-text.
- **Planner**: LLM for task decomposition.
- **Vision & Action**: Vision-Language Model (VLM) for semantic UI grounding.
- **Control**: ADB + WebRTC for real-time cloud phone streaming and interaction.

## Goal
To build an age-friendly solution that handles complex app interactions, with strict human-in-the-loop checkouts and graceful fallback mechanisms for connectivity drops.
