#!/bin/zsh
cd "${0:A:h}"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [[ -f data/cloud-worker.json ]]; then
  exec /usr/bin/caffeinate -i /usr/bin/python3 cloud/worker.py
fi
exec /usr/bin/caffeinate -i /usr/bin/python3 server.py
