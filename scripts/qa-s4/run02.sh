pip install -q --break-system-packages playwright==1.63.0 2>&1 | tail -1
python3 /w/rnf02.py "$@"
