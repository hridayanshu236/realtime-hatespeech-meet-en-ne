#!/bin/bash
# setup_kaggle_env.sh
# Quickly recreates the directory structure on a fresh Kaggle session

echo "Setting up project structure..."
mkdir -p data/raw/{jigsaw,davidson,hatexplain}
mkdir -p data/processed
mkdir -p data/merged
mkdir -p models/baselines/mbert
mkdir -p models/xlm_roberta/checkpoints
mkdir -p models/xlm_roberta/final
mkdir -p notebooks
mkdir -p src
mkdir -p results

echo "Project structure created."
