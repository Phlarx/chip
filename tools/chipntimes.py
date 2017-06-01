#!/usr/bin/python3

""" Chip N Times
Create a Chip circuit that terminates after N cycles.
"""

from sys import argv, stderr

if len(argv) == 1:
        print('Usage: %s [-k] <iters>\n\n\t-k\tEnable caching every 8 bits, with the K element\n\titers\tThe number of iterations for the circuit to run before termination' % (argv[0]), file=stderr)
        exit(-1)

cacheline = ''
if argv[1] == '-k':
	cacheline = '\n K  K'

seq = bin(int(argv[-1]))[2:]
out = ' *'
for i,bit in enumerate(seq[::-1]):
	if i != 0 and i%8 == 0:
		out += cacheline
	out += '\n,xZ'
	out += ('~' if bit == '1' else '-')
	out += "<\n`@' |"
out += '\n    `~T'

print(out)
