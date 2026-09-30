pip install -q --break-system-packages playwright==$PWV 2>&1 | grep -v WARNING | tail -1
python3 /w/ui.py "$@"
