set shell := ["bash", "-cu"]

venv_dir := ".venv"
python := venv_dir + "/bin/python"

default:
	@just --list

create:
	if [ ! -d "{{venv_dir}}" ]; then uv venv; fi

install: create
	source "{{venv_dir}}/bin/activate"
	uv pip install -e .

run: install
	{{python}} -m streamlit run webapp/app.py