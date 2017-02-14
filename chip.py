#!/usr/bin/python3
#coding=utf-8
#author Derek Anderson
#interpreter v0.1.2

from sys import argv, stdin, stdout, stderr, exit
from getopt import getopt, GetoptError
from optparse import OptionParser

import chiplib

DEFAULT_VALUE = bytes([0])
IGNORE_EOF = False
NEWLINE = False
VERBOSE = False
WITHOUT_STDIN = False

def init():
	"""Perform initialization tasks"""
	global DEFAULT_VALUE
	global IGNORE_EOF
	global NEWLINE
	global VERBOSE
	global WITHOUT_STDIN

	def version_callback(option, opt, value, parser):
		parser.print_version()
		exit(0)

	parser = OptionParser(usage='Usage: %prog [-hnovVwz] <chipspec>', version='%prog 0.1.2', conflict_handler='resolve')
	parser.add_option('-n', '--extra-newline', action='store_true', dest='extra_newline', default=False, help='provides an extra newline to STDOUT at the end of execution, regardless of the method of termination')
	parser.add_option('-o', '--ignore-eof-ones', action='store_true', dest='ignore_eof_o', default=False, help='when input is exhausted, instead of terminating, provides one values (0xff) until the circuit terminates itself')
	parser.add_option('-v', '--verbose', action='store_true', dest='verbose', default=False, help='enables verbose output; shows the parsed circuitry and input/output for each cycle')
	parser.add_option('-V', '--version', action='callback', callback=version_callback, help="show interpreter's version number and exit")
	parser.add_option('-w', '--without-stdin', action='store_true', dest='without', default=False, help='the program uses the default value (set by -z or -o), instead of reading from STDIN. By itself, implies -z')
	parser.add_option('-z', '--ignore-eof', action='store_true', dest='ignore_eof_z', default=False, help='when input is exhausted, instead of terminating, provides zero values (0x00) until the circuit terminates itself')
	opts, args = parser.parse_args()

	IGNORE_EOF = opts.ignore_eof_z or opts.ignore_eof_o
	NEWLINE = opts.extra_newline
	VERBOSE = opts.verbose
	WITHOUT_STDIN = opts.without

	if opts.ignore_eof_o:
		DEFAULT_VALUE = bytes([255])
	else:
		DEFAULT_VALUE = bytes([0])

	if len(args) == 1:
		with open(args[0], 'r') as f:
			arr = f.readlines()
			if len(arr) > 0 and arr[0].startswith("#!"):
				# Its a shebang, probably. Remove the whole line.
				arr = arr[1:]
			return ''.join(arr)
	else:
		parser.print_help()
		exit(2)

def setup(ospec):
	"""Prepare the circuitry from the text specification"""
	spec = list(ospec)
	# Cleanup comments and check symbols
	charlist = ''.join(chiplib.lexmap.keys())
	blockcomment = False
	layercomment = False
	for char in range(len(spec)):
		if spec[char] == '\n':
			layercomment = False
		elif blockcomment and spec[char] == ';':
			blockcomment = False
			spec[char] = ' '
		elif spec[char] == '=' and (char == 0 or spec[char-1] == '\n'):
			layercomment = True
		elif spec[char] == ':':
			blockcomment = True
			spec[char] = ' '
		elif blockcomment or layercomment:
			spec[char] = ' '
		else:
			# Check if a valid char
			msg = None
			if spec[char] == '=':
				msg = "'=' must only be found at the beginning of a line, or in a comment"
			elif spec[char] == ';':
				msg = "';' must only be used to terminate a block comment, or found within a layer comment"
			elif spec[char] not in charlist:
				msg = "'%s' (%d) is not a valid character" % (spec[char], ord(spec[char]))
			if msg:
				slice = ''.join(spec[:char])
				row = slice.count('\n')+1
				col = len(slice) - slice.rfind('\n')
				stderr.write("%d:%d WARN: %s\n" % (row, col, msg))
				spec[char] = ' '
	spec = list(map(lambda x:x.rstrip(), ''.join(spec).split('\n')))
	# Cleanup unnecessary lines
	layertail = True
	for line in range(len(spec)-1, -1, -1):
		if spec[line] == '':
			if layertail:
				spec = spec[:line] + spec[line+1:]
			else:
				pass
		elif spec[line] == '=':
			layertail = True
		else:
			layertail = False
	if len(spec) > 0 and spec[0] == '=':
		spec = spec[1:]
	spec = '\n'.join(spec)

	# Convert to final layout
	spec2 = list(map(lambda s: s[(1 if len(s) > 0 and s[0] == '\n' else None):].rstrip('\n'), spec.split('=')))
	n = max(map(lambda s:s.count('\n'), spec2))
	spec2 = list(map(lambda s:(s+('\n'*(n-s.count('\n')))).split('\n'), spec2))
	n = max(map(lambda s:max(map(len, s)), spec2))
	spec2 = list(map(lambda s:list(map(lambda t:list(t+(' '*(n-len(t)))), s)), spec2))

	board = chiplib.Board()
	board.initialize([[[chiplib.getElementType(char)(board, x, y, z, char) for x,char in enumerate(row)] for y,row in enumerate(layer)] for z,layer in enumerate(spec2)])
	if VERBOSE:
		stderr.write(str(board) + '\n')

	def circuit_gen():
		"""A generator representing the board's state and function"""
		outbits = None
		status = 0
		debug = ''
		try:
			while True:
				inbits = yield (status, outbits, debug)
				status, outbits, debug = board.run(inbits)
		except KeyboardInterrupt as e:
			if VERBOSE:
				stderr.write('\n' + str(board))
			stderr.write('\nStack: ')
			if board.stack:
				if VERBOSE or len(board.stack) < 9:
					stderr.write(' '.join(map(lambda v:''.join(map(str, v)), board.stack[::-1])))
				else:
					stderr.write(' '.join(map(lambda v:''.join(map(str, v)), board.stack[:-9:-1])))
					stderr.write(' ... ')
					stderr.write(str(len(board.stack)-8))
					stderr.write('more')
			else:
				stderr.write('empty')
			stderr.write('\nAge: ')
			stderr.write(str(board.age))
			stderr.write('\n')

	# Start up the circuit
	circuit = circuit_gen()
	circuit.send(None)

	return circuit

def run(circuit):
	"""Run the circuit for each input byte"""
	if VERBOSE:
		stderr.write('        HGFEDCBA        hgfedcba\n')
	status = 0
	inchar = DEFAULT_VALUE
	try:
		while True:
			# Read input, plus eof check
			if not (status & chiplib.Board.READ_HOLD):
				if WITHOUT_STDIN:
					inchar = DEFAULT_VALUE
				else:
					inchar = stdin.buffer.read(1)
					if len(inchar) == 0:
						# EOF
						if IGNORE_EOF:
							inchar = DEFAULT_VALUE
						else:
							break
			inbin = bin(ord(inchar))[2:]
			inbits = list(map(int, '0'*(8-len(inbin)) + inbin))[::-1]
			if VERBOSE:
				if not (status & chiplib.Board.READ_HOLD):
					if 0 <= inchar[0] < 32 or inchar[0] == 127:
						inc = '�'
					else:
						inc = inchar.decode('utf-8', 'replace')
					stderr.write('     %s\t%s  →' % (inc, ''.join(map(str, inbits[::-1]))))
				else:
					stderr.write('                  →')
	
			# Execute a clock cycle
			status, outbits, debug = circuit.send(inbits)
	
			# Output
			outchar = bytes([int(''.join(map(str, outbits[::-1])), 2)])
			if VERBOSE:
				if not (status & chiplib.Board.WRITE_HOLD):
					if 0 <= outchar[0] < 32 or outchar[0] == 127:
						outc = '�'
					else:
						outc = outchar.decode('utf-8', 'replace')
					stderr.write('  %s\t%s' % (outc, ''.join(map(str, outbits[::-1]))))
				else:
					stderr.write('             ')
				if debug:
					stderr.write('\t%s' % debug)
				stderr.write('\n')
			if not (status & chiplib.Board.WRITE_HOLD):
				stdout.buffer.write(outchar)
	
			# Early termination
			if (status & chiplib.Board.TERMINATE):
				break
		if VERBOSE:
			stderr.write('\n')
	except StopIteration as e:
		stderr.write('Execution halted\n')
	if NEWLINE:
		stdout.write('\n')

if __name__ == '__main__':
	spec = init()
	circuit = setup(spec)
	run(circuit)
