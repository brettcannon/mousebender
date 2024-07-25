#!/bin/sh
LOCK_FILE_PATH=pylock.example.toml
echo "Lock the example in $LOCK_FILE_PATH ..."
py . lock --platform cpython3.12-manylinux2014-x64 --platform cpython3.12-windows-x64 "numpy<2" mousebender hatchling requests pydantic trio > $LOCK_FILE_PATH

echo "Install from $LOCK_FILE_PATH ..."
py . install $LOCK_FILE_PATH
