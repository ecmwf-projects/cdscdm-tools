
MODULE := cdstoolbox
ENV := CDSTOOLBOX

test:
	pytest -v --cov=. --cov-report=html .

create:
	conda env create -n $(ENV) -f environment.in.yml
	conda install -n $(ENV) pytest pytest-cov

update:
	conda env update -n $(ENV) -f environment.in.yml
	conda install -n $(ENV) pytest pytest-cov

