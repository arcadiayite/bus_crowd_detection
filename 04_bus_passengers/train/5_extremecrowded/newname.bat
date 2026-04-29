@echo off
setlocal enabledelayedexpansion

for %%f in (4*) do (
	set "name=%%f"
	set "newname=5!name:~1"
	ren "%%f" "newname!"
)

echo Done.
pause