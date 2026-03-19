set HTTPS_PROXY=http://127.0.0.1:7890
set HTTP_PROXY=http://127.0.0.1:7890
cd C:\Users\Administrator\Desktop\apikey-manager
del _create.bat _push.bat
git add -A
git commit -m "Remove temp scripts"
git push 2>&1
