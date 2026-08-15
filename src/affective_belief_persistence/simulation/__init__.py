"""Deterministic forty-day simulation harness.

The package intentionally performs no eager imports: schema generation imports
individual simulation contracts while the core configuration module is still
initializing. Import public APIs from their explicit submodules.
"""
