#!/bin/sh
echo "Lock graph example ..."
GRAPH_TOML=pylock.graph-example.toml
py . lock numpy mousebender hatchling requests pydantic > $GRAPH_TOML
echo "Generate graph ..."
py . graph --self-contained $GRAPH_TOML > pylock.graph-example.md

echo "Initial 'maximize' example ..."
COMPATIBILITY_TOML=pylock.compatibility-example.toml
py . lock debugpy > $COMPATIBILITY_TOML
echo "Add compatibility lock entry ..."
py . add-lock-entry --platform python3.12 $COMPATIBILITY_TOML > /dev/null
