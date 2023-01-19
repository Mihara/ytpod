#!/bin/bash

# I cannot currently be bothered with a makefile.
# This should produce an executable from scratch.
# It assumes you already have the correct virtualenv activated.

pip install --upgrade .[binary]

mkdir -p dist

shiv -c ytpod -o dist/ytpod .
