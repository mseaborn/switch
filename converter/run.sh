#!/bin/bash

set -eu

export PYTHONPATH=$(cd .. && pwd)

rm -rf inputs

python convert_example.py
echo done
