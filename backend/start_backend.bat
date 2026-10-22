@echo off
setlocal
cd /d "%~dp0"
if defined JAVA_HOME set "PATH=%JAVA_HOME%\bin;%PATH%"
set "MAVEN=%~dp0..\tools\maven-runtime\apache-maven-3.9.12\bin\mvn.cmd"
if exist "%MAVEN%" goto run
set "MAVEN=mvn.cmd"
:run
call "%MAVEN%" spring-boot:run
if errorlevel 1 pause
