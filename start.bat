@echo off
cd /d "%~dp0"
echo ================================================
echo  LLM Wiki - Full Refresh
echo ================================================
echo.
echo [0/4] Checking Ollama server...
curl -s http://127.0.0.1:11434 >nul 2>&1
if errorlevel 1 (
    echo   Ollama not running. Starting in background...
    start /min "Ollama" ollama serve
    echo   Waiting 5 seconds for Ollama to start...
    timeout /t 5 /nobreak >nul
    curl -s http://127.0.0.1:11434 >nul 2>&1
    if errorlevel 1 (
        echo   [WARN] Ollama may not be ready. Continuing anyway...
    ) else (
        echo   Ollama started OK.
    )
) else (
    echo   Ollama already running. OK.
)
echo.
echo [1/4] Checking dependencies...
python -c "import graphify" >nul 2>&1
if errorlevel 1 (
    echo   Installing graphifyy...
    python -m pip install graphifyy networkx -q
    if errorlevel 1 (echo [ERROR] graphifyy install failed. & pause & exit /b 1)
)
echo   OK.
echo.
echo [2/4] Graphify AST extraction (all 9 projects, 0 tokens)...
python scripts/graphify_run.py
echo.
echo [3/4] AI summaries + knowledge graph + home page...
python scripts/ingest.py
python scripts/build_graph.py
python scripts/build_home.py
if errorlevel 1 (echo [ERROR] Rebuild failed. & pause & exit /b 1)
echo.
echo [4/4] Opening browser...
start "" "%~dp0Wiki\home.html"
echo.
echo ================================================
echo  Done! Wiki home.html opened in browser.
echo ================================================
echo.
pause
