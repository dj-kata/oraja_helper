wuv=/mnt/c/Users/katao/.local/bin/uv.exe
project_name=oraja_helper
target=$(project_name)/viewer.exe
target_zip=$(project_name).zip
srcs=$(subst update.py,,$(wildcard *.py)) $(wildcard *.pyw)
html_files=$(wildcard html/*.*)

all: $(target_zip)
$(target_zip): $(target) $(project_name)/update.exe $(html_files) version.txt
	@cp version.txt $(project_name)
	@cp -a html $(project_name)
	@rm -rf $(project_name)/log
	@zip $(target_zip) $(project_name)/* $(outdir)/*/*

$(target): $(srcs)
	@$(wuv) run pyarmor -d gen --output=$(project_name) --pack onefile otoge_input_viewer.pyw
$(project_name)/update.exe: update.py
	@$(wuv) run pyarmor -d gen --output=$(project_name) --pack onefile $<

dist: 
	@cp -a html to_bin/
	@cp -a version.txt to_bin/
	@cp -a $(project_name)/*.exe to_bin/

clean:
	@rm -rf $(target)
	@rm -rf $(project_name)/update.exe
	@rm -rf __pycache__
	@rm -rf pyarmor*log

test:
	@$(wuv) run $(project_name).pyw
