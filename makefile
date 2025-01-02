build: pyproject.toml
#	pip-compile > requirements.txt
#	pip-sync
	pipx install -e .
	pre-commit install
