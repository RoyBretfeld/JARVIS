@echo off
echo Aktiviere virtuelle Umgebung...
call .\venv_py310_gpu\Scripts\activate.bat

echo Erstelle Icon...
python create_icon.py

echo Aktualisiere Desktop-Verknüpfung...
set SCRIPT="%TEMP%\update_jarvis_shortcut.vbs"
echo Set oWS = WScript.CreateObject("WScript.Shell") > %SCRIPT%
echo sLinkFile = "%USERPROFILE%\Desktop\JARVIS.lnk" >> %SCRIPT%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %SCRIPT%
echo oLink.TargetPath = "%~dp0start_jarvis.bat" >> %SCRIPT%
echo oLink.WorkingDirectory = "%~dp0" >> %SCRIPT%
echo oLink.Description = "JARVIS - KI-Assistent" >> %SCRIPT%
echo oLink.IconLocation = "%~dp0icon.ico" >> %SCRIPT%
echo oLink.Save >> %SCRIPT%

"C:\Windows\System32\cscript.exe" /nologo %SCRIPT%
del %SCRIPT%

echo Icon wurde erfolgreich aktualisiert!
pause 