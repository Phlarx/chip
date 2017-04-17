#!/usr/bin/python3
#coding=utf-8

""" Chip Word
This script will generate a Chip specification to print out the given
words. Each byte is encoded by how it differs from the previous byte.
"""

from sys import argv, stderr

""" Toggle this flag to bias the output in the opposite direction """
ltr = False

if len(argv) == 1:
	print('Usage: %s <phrase...>\n\n\tphrase\tA phrase (multiple args are joined with space)' % (argv[0]), file=stderr)
	exit(-1)

word = ' '.join(argv[1:])

def x(s,m):
	t = [ord(c) & m for c in s]
	return zip(t[:-1], t[1:])

if ltr:
	w = '\0' + word

	p = "*s\n`" + ("Zv" * (len(word)-1)) + "t"
	h = "\nh" + "/".join([("-" if a==b else "÷") for a,b in x(w, 0x80)])
	g = "\ng" + "/".join([("-" if a==b else "÷") for a,b in x(w, 0x40)])
	f = "\nf" + "/".join([("-" if a==b else "÷") for a,b in x(w, 0x20)])
	e = "\ne" + "/".join([("-" if a==b else "÷") for a,b in x(w, 0x10)])
	d = "\nd" + "/".join([("-" if a==b else "÷") for a,b in x(w, 0x08)])
	c = "\nc" + "/".join([("-" if a==b else "÷") for a,b in x(w, 0x04)])
	b = "\nb" + "/".join([("-" if a==b else "÷") for a,b in x(w, 0x02)])
	a = "\na" + "/".join([("-" if a==b else "÷") for a,b in x(w, 0x01)])

else:
	w = word[::-1] + '\0'

	p = "t" + ("vz" * (len(word)-1)) + "-*s\n"
	h = "/".join([("-" if a==b else "~") for a,b in x(w, 0x80)]) + "h\n"
	g = "/".join([("-" if a==b else "~") for a,b in x(w, 0x40)]) + "g\n"
	f = "/".join([("-" if a==b else "~") for a,b in x(w, 0x20)]) + "f\n"
	e = "/".join([("-" if a==b else "~") for a,b in x(w, 0x10)]) + "e\n"
	d = "/".join([("-" if a==b else "~") for a,b in x(w, 0x08)]) + "d\n"
	c = "/".join([("-" if a==b else "~") for a,b in x(w, 0x04)]) + "c\n"
	b = "/".join([("-" if a==b else "~") for a,b in x(w, 0x02)]) + "b\n"
	a = "/".join([("-" if a==b else "~") for a,b in x(w, 0x01)]) + "a"

print(p + h + g + f + e + d + c + b + a)
