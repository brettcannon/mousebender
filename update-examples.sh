#!/bin/sh
GRAPH_TOML=pylock.graph-example.toml
echo "Lock the graph example in $GRAPH_TOML ..."
py . lock numpy mousebender hatchling requests pydantic > $GRAPH_TOML
GRAPH_MD=pylock.graph-example.md
echo "Generate the graph in $GRAPH_MD ..."
py . graph --self-contained $GRAPH_TOML > $GRAPH_MD

COMPATIBILITY_TOML=pylock.compatibility-example.toml
echo "Start a compatibility example for CPython 3.10 manylinux2014 x64 in $COMPATIBILLITY_TOML ..."
py . lock --platform cpython3.10-manylinux2014-x64 debugpy > $COMPATIBILITY_TOML
echo "Add CPython 3.12 Windows x64 lock entry ..."
py . add-lock-entry --platform cpython3.12-windows-x64 $COMPATIBILITY_TOML > /dev/null
echo "Add pure Python 3.12 lock entry ..."
py . add-lock-entry --platform python3.12 $COMPATIBILITY_TOML > /dev/null

echo "Install from $COMPATIBILITY_TOML ..."
py . install $COMPATIBILITY_TOML
