#!/usr/bin/python3
#coding=utf-8

""" Chip Word
This script will generate a Chip specification to print out the given
words. Each bit is encoded as `)` for 1 and `x` for 0.
"""

from sys import argv, stderr

if len(argv) == 1:
	print('Usage: %s <phrase...>\n\n\tphrase\tA phrase (multiple args are joined with space)' % (argv[0]), file=stderr)
	exit(-1)

word = ' '.join(argv[1:])

def x(s,m):
	t = [ord(c) & m for c in s]
	return zip(t[:-1], t[1:])

p = "*Z~.\n,--'\n>" + ("Z" * (len(word)-1)) + "t\n"
h = "".join([(")" if ord(x) & 0x80 else "x") for x in word]) + "h\n"
g = "".join([(")" if ord(x) & 0x40 else "x") for x in word]) + "g\n"
f = "".join([(")" if ord(x) & 0x20 else "x") for x in word]) + "f\n"
e = "".join([(")" if ord(x) & 0x10 else "x") for x in word]) + "e\n"
d = "".join([(")" if ord(x) & 0x08 else "x") for x in word]) + "d\n"
c = "".join([(")" if ord(x) & 0x04 else "x") for x in word]) + "c\n"
b = "".join([(")" if ord(x) & 0x02 else "x") for x in word]) + "b\n"
a = "".join([(")" if ord(x) & 0x01 else "x") for x in word]) + "a"

print(p + h + g + f + e + d + c + b + a)
