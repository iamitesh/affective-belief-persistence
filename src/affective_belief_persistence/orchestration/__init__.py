"""Typed, deterministic multi-agent orchestration for the 48-hour sprint.

Public objects live in their focused modules. Keeping package import side effects
at zero is important because the foundation configuration module owns schema
loading and is imported before the supervisor in the CLI.
"""
