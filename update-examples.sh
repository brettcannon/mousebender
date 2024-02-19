#!/bin/sh
py . lock numpy mousebender hatchling requests pydantic > pylock.graph-example.toml
py . graph --self-contained pylock.graph-example.toml > pylock.graph-example.md

py . lock debugpy > pylock.maximize-example.toml
py . add-lock --maximize compatibility pylock.maximize-example.toml > /dev/null
