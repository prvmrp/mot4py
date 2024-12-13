build: pyproject.toml
	pip-compile > requirements.txt
	pip-sync
	pip install -e .
