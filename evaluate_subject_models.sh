#!/bin/bash
#SBATCH -N 1
#SBATCH -c 1
#SBATCH --gres=gpu:1
#SBATCH -p res-gpu-small
#SBATCH --qos=short
#SBATCH --time=0-00:10:00

source /etc/profile
module load cuda/11.7
source /home2/wclv88/bounding-mi/bounding-mi/bin/activate
stdbuf -oL /home2/wclv88/bounding-mi/bounding-mi/bin/python train_subject_models.py --path=subject_models --load_model_idx=7004
