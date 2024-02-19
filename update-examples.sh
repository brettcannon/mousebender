#!/bin/sh
echo "Lock graph example ..."
py . lock numpy mousebender hatchling requests pydantic > pylock.graph-example.toml
echo "Generate graph ..."
py . graph --self-contained pylock.graph-example.toml > pylock.graph-example.md

echo "Initial 'maximize' example ..."
py . lock debugpy > pylock.maximize-example.toml
echo "Add compatibility lock entry ..."
py . add-lock-entry --maximize compatibility pylock.maximize-example.toml > /dev/null
