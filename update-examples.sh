#!/bin/sh
echo "Lock graph example ..."
GRAPH_TOML=pylock.graph-example.toml
py . lock numpy mousebender hatchling requests pydantic > $GRAPH_TOML
echo "Generate graph ..."
py . graph --self-contained $GRAPH_TOML > pylock.graph-example.md

echo "Initial 'maximize' example for CPython 3.10 manylinux2014 x64 ..."
COMPATIBILITY_TOML=pylock.compatibility-example.toml
py . lock --platform cpython3.10-manylinux2014-x64 debugpy > $COMPATIBILITY_TOML
echo "Add CPython 3.12 Windows x64 lock entry ..."
py . add-lock-entry --platform cpython3.12-windows-x64 $COMPATIBILITY_TOML > /dev/null
echo "Add compatibility lock entry ..."
py . add-lock-entry --platform python3.12 $COMPATIBILITY_TOML > /dev/null
