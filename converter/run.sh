#!/bin/bash
# Copyright 2016 The Switch Authors. All rights reserved.
# Licensed under the Apache License, Version 2, which is in the LICENSE file.

set -eu

export PYTHONPATH=$(cd .. && pwd)

rm -rf inputs
rm -rf outputs

python v2_example.py
echo done
