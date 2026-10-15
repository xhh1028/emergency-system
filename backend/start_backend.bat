@echo off
set "JAVA_HOME=D:\software\intellij_IDEA\DJK17"
set "PATH=%JAVA_HOME%\bin;%PATH%"
cd /d "D:\College_Innovation_Pregram\backend"
"D:\College_Innovation_Pregram\AAAAAAemergency-system(4)\.tools\apache-maven-3.9.12\bin\mvn.cmd" spring-boot:run > "D:\College_Innovation_Pregram\backend\backend_run.log" 2>&1
