# Build and serve the documentation. Stop with Ctrl+C; rerun after edits.
docs port="8000":
    make build
    python3 -m http.server {{port}} --bind 0.0.0.0 --directory _build/html
