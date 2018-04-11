from __future__ import print_function
import subprocess
import os
import sys
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('base',
        help='location of directory containing larpix-scripts, '
        'larpix-control, etc.')
args = parser.parse_args()

def git_describe(directory):
    current_dir = os.getcwd()
    os.chdir(directory)
    output = subprocess.check_output(['git', 'describe', '--always',
        '--long'])
    os.chdir(current_dir)
    return output.decode()

def git_diff(directory):
    current_dir = os.getcwd()
    os.chdir(directory)
    output = subprocess.check_output(['git', 'diff'])
    os.chdir(current_dir)
    return output.decode()

def pip_show(package):
    output = subprocess.check_output(['pip', 'show', package])
    return output.decode()

to_save = []
print('Preparing bug report')
print('Collecting system info')
to_save.append('Platform: ' + sys.platform)
current_dir = os.getcwd()
os.chdir(args.base)
to_save.append('larpix-control HEAD: ' + git_describe('larpix-control'))
to_save.append('larpix-control diff:\n' + git_diff('larpix-control'))
to_save.append('larpix-scripts HEAD: ' + git_describe('larpix-scripts'))
to_save.append('larpix-scripts diff:\n' + git_diff('larpix-scripts'))
to_save.append('pip show larpix-control:\n' +
        pip_show('larpix-control'))
to_save.append('pip show larpix-geometry:\n' +
        pip_show('larpix-geometry'))
os.chdir(current_dir)

outfile = 'bugreport.txt'
with open(outfile, 'w') as f:
    print('Saving to: ' + os.path.abspath(f.name))
    f.write('\n'.join(to_save))
