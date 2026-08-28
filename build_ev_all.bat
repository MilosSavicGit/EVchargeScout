@echo off
REM ============================================================
REM  build_ev_all.bat -- bulk EV charger build (Open Charge Map)
REM
REM  The country list now lives in build_ev.py, so this is just a
REM  convenience wrapper. One call does the lot, with paging and
REM  polite pauses handled inside the script.
REM
REM  THE API KEY IS NO LONGER IN THIS FILE. The previous version had
REM  it in plain text, which is why it had to be gitignored -- and a
REM  gitignored file is one `git add -f` away from being public.
REM  Set it once as a Windows user environment variable instead:
REM
REM      setx OCM_API_KEY "your-key-here"
REM
REM  then open a NEW terminal (setx does not affect the current one).
REM  Get a key at https://openchargemap.org/site/profile/applications
REM ============================================================

if "%OCM_API_KEY%"=="" (
  echo.
  echo   OCM_API_KEY is not set.
  echo   Run:  setx OCM_API_KEY "your-key-here"
  echo   then open a new terminal and try again.
  echo.
  pause
  exit /b 1
)

echo.
echo ==== Full rebuild: every country ====
python build_ev.py --all
goto done

REM ---- other modes, uncomment as needed -------------------------
REM  Weekly delta -- only what changed since each file was built:
REM     python build_ev.py --all --since auto
REM  One country:
REM     python build_ev.py --country DE
REM  Delta from a fixed date:
REM     python build_ev.py --all --since 2026-08-01
REM ---------------------------------------------------------------

:done
echo.
echo ============================================================
echo  Done. EV charger files are in the  ev\  folder.
echo  data (C) Open Charge Map contributors
echo ============================================================
pause
