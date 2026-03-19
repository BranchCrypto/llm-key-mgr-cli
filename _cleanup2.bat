set HTTPS_PROXY=http://127.0.0.1:7890
set HTTP_PROXY=http://127.0.0.1:7890
cd C:\Users\Administrator\Desktop\apikey-manager
del _cleanup.bat
git add -A
git commit -m "Remove last temp script"
git push 2>&1
