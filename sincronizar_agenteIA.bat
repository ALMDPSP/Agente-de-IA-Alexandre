@echo off
setlocal
chcp 65001 >nul
title Sincronizar conhecimento - Alexandre AI
color 0A

echo ============================================================
echo        ALEXANDRE AI - SINCRONIZAR C:\agenteIA
echo ============================================================
echo.

if "%AGENT_URL%"=="" (
  echo ERRO: variavel AGENT_URL nao configurada.
  echo Exemplo: setx AGENT_URL "https://seu-servico.onrender.com"
  goto :fim
)

if "%SYNC_TOKEN%"=="" (
  echo ERRO: variavel SYNC_TOKEN nao configurada.
  echo Configure o mesmo token usado na versao online.
  goto :fim
)

if not exist "C:\agenteIA\" (
  echo ERRO: pasta C:\agenteIA nao encontrada.
  goto :fim
)

python "%~dp0sync_local_knowledge.py"

:fim
echo.
pause
