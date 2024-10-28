#!/bin/bash

# source "$HOME/miniconda3/etc/profile.d/conda.sh"
eval "$(conda shell.bash hook)"

conda activate veggie

tmux new-session -d -s users 'python ../search_user/search_user.py'
tmux new-session -d -s orders 'python ../search_order/search_order.py'
tmux new-session -d -s product 'python ../search_product/search_product.py'
