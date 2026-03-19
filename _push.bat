set HTTPS_PROXY=http://127.0.0.1:7890
set HTTP_PROXY=http://127.0.0.1:7890
cd C:\Users\Administrator\Desktop\apikey-manager
git add -A
git commit -m "Rename project to llm-key-mgr-cli"
git remote set-url origin https://github.com/BranchCrypto/llm-key-mgr-cli.git
git push -u origin main --force 2>&1
