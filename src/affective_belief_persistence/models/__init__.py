"""Model-runner package.

The package initializer intentionally performs no eager imports.  Central
schema generation imports ``models.contracts`` while the legacy adapter imports
the root schemas, so eager re-exports here would create an initialization cycle.
Import public APIs from their defining modules.
"""
