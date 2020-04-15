
MODULE := cdstoolbox

create:
	conda env create -f environment.yml

update:
	conda env update -f environment.yml

test:
	pytest -vv --flakes --cov $(MODULE) --cov-report html .
