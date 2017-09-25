#!/usr/bin/python3
#coding=utf-8

""" Chip Mirror
This script attempts to horizontally flip a Chip specification
letf-to-right. No guarantees are made to the correctness of the
result. Comment text will be mangled, and multiline comments are not
properly handled.
"""

from sys import argv, stderr

i = []
o = []

table = str.maketrans(
	"#@[]Zz»«LR←→Mm⌐~¬÷()>├<┤`└'┘,┌.┐{}:;",
	"@#][zZ«»RL→←mM¬÷⌐~)(<┤>├'┘`└.┐,┌}{;:"
)

if len(argv) != 2:
	print('Usage: %s <spec>\n\n\tspec\tA valid Chip specification' % (argv[0]), file=stderr)
	exit(-1)

with open(argv[1], 'r') as f:
	for line in f:
		i.append(line.strip('\n'))

if len(i) == 0:
	print('WARN: Input spec is empty file', file=stderr)
	exit(0)

if i[0].startswith("#!"):
	o.append(i.pop(0))

width = max(map(len, i))

for line in i:
	if line.startswith("="):
		o.append(line)
	else:
		full = line + ' '*(width - len(line))
		rev = full[::-1].rstrip()
		o.append(rev.translate(table))

print('\n'.join(o))
