import subprocess, os
os.chdir(r'C:\Users\Administrator\apikey-manager')
subprocess.run(['git', 'add', '-A'], check=True)
subprocess.run(['git', 'commit', '-m', 'chore: remove temp scripts'], check=True)
subprocess.run(['git', 'push', 'origin', 'main'], check=True)
print('Cleaned and pushed!')
