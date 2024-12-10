#!/bin/bash

## this script is used to start all microservices locally for testing

# source "$HOME/miniconda3/etc/profile.d/conda.sh"
eval "$(conda shell.bash hook)"

conda activate veggie

restart_tmux_session() {
    session_name=$1
    command=$2

    # Check if the session already exists
    if tmux has-session -t "$session_name" 2>/dev/null; then
        echo "Session $session_name already exists. Killing it..."
        tmux kill-session -t "$session_name"
    fi

    # Start the new session
    echo "Starting new session $session_name..."
    tmux new-session -d -s "$session_name" "$command"
}

restart_tmux_session "composite" "python ~/cloudComputing/ebayClone/user/app.py 8891"

# Restart the user service
cd ~/cloudComputing/ebayClone/user
restart_tmux_session "user" "python ~/cloudComputing/ebayClone/user/app.py 8889"

# Restart the order service
cd ~/cloudComputing/ebayClone/order
restart_tmux_session "order" "python ~/cloudComputing/ebayClone/order/app.py 8890"

# Restart the product service
cd ~/cloudComputing/ebayClone/product
restart_tmux_session "product" "python ~/cloudComputing/ebayClone/product/app.py 8888"
