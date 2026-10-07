#!/bin/zsh
cd "${0:A:h}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
exec /usr/bin/caffeinate -i /usr/bin/python3 cloud/worker.py
