import subprocess, os
os.chdir(r'C:\Users\Administrator\apikey-manager')
subprocess.run(['git', 'add', '-A'], check=True)
subprocess.run(['git', 'commit', '-m', 'fix: Protocol.parse_protocol -> KeyEntry.parse_protocol'], check=True)
subprocess.run(['git', 'push', 'origin', 'main', '--force'], check=True)
print('Pushed!')
