#!/usr/bin/python3
#coding=utf-8

""" Chip Word
This script will generate a Chip specification to print out the given
words. Each bit is encoded as `)` for 1 and `x` for 0.
"""

from sys import argv, stderr

if len(argv) == 1 or argv[1] == "-h":
	print('''Usage: %s [--] <phrase...>
       %s -f <filename>

	phrase
		A phrase. Multiple args are joined with space.
	filename
		A file from which to read the phrase. Additional args are not processed.'''
	      % (argv[0], argv[0]), file=stderr)
	exit(-1)
if argv[1] == "--":
	word = ' '.join(argv[2:])
elif argv[1] == "-f" and len(argv) >= 3:
	with open(argv[2]) as f:
		word = f.read()
elif argv[1][:2] == "-f":
	with open(argv[1][2:]) as f:
		word = f.read()
else:
	word = ' '.join(argv[1:])

word = bytes(word, 'UTF8')

p = []
h = []
g = []
f = []
e = []
d = []
c = []
b = []
a = []

# If we are dealing with >128 bytes, we'll split it up into chunks.
# The last chunk (or only chunk) may be less that 128 bytes long.
for chunk in [word[i:i+128] for i in range(0, len(word), 128)]:
	p += ["Z" * (len(chunk)-1)]
	h += ["".join([(")" if x & 0x80 else "x") for x in chunk]) + "h"]
	g += ["".join([(")" if x & 0x40 else "x") for x in chunk]) + "g"]
	f += ["".join([(")" if x & 0x20 else "x") for x in chunk]) + "f"]
	e += ["".join([(")" if x & 0x10 else "x") for x in chunk]) + "e"]
	d += ["".join([(")" if x & 0x08 else "x") for x in chunk]) + "d"]
	c += ["".join([(")" if x & 0x04 else "x") for x in chunk]) + "c"]
	b += ["".join([(")" if x & 0x02 else "x") for x in chunk]) + "b"]
	a += ["".join([(")" if x & 0x01 else "x") for x in chunk]) + "a"]

print("\n".join(["*Z~.\n,--'\n>" + "-KZ".join(p) + "t",
		 " ".join(h), " ".join(g),
		 " ".join(f), " ".join(e),
		 " ".join(d), " ".join(c),
		 " ".join(b), " ".join(a)]))
