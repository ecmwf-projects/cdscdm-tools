
MODULE := cdscdm_tools
ENV := CDSCDM-TOOLS

test:
	pytest -v --cov=. --cov-report=html .

qa:
	flake8 .
	mypy --strict .

env-create:
	conda env create -n $(ENV) -f environment.in.yml
	conda install -n $(ENV) pytest pytest-cov
	conda install -n $(ENV) mypy flake8

env-update:
	conda env update -n $(ENV) -f environment.in.yml
	conda update -n $(ENV) pytest pytest-cov || conda install -n $(ENV) pytest pytest-cov
	conda update -n $(ENV) mypy flake8 || conda install -n $(ENV) mypy flake8

