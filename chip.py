#!/usr/bin/python3 -bb
#coding=utf-8
#author Derek Anderson
#interpreter v0.1.4

from sys import argv, stdin, stdout, stderr, exit
from getopt import getopt, GetoptError
from optparse import OptionParser

import time, termios, tty
import chiplib

class ConfigDict(dict):
	def __getattr__(self, name):
		return self[name]
	def __setattr__(self, name, value):
		if name in self:
			self[name] = value
		else:
			raise KeyError(name)
Cfg = ConfigDict(
	DEFAULT_VALUE=bytes([0]),
	ESC_SEQS=tuple(),
	IGNORE_EOF=False,
	NEWLINE=False,
	NO_BUFFER=False,
	VERBOSE=False,
	WITHOUT_STDIN=False
)

def init():
	"""Perform initialization tasks"""

	def version_callback(option, opt, value, parser):
		parser.print_version()
		exit(0)

	parser = OptionParser(usage='Usage: %prog [options] <chipspec>', version='%prog 0.1.4', conflict_handler='resolve')
	parser.add_option('-e', '--escape', action='append', dest='esc_seqs', help='Use these characters as escape sequences for input. A default of ^C and ^D are included in immediate mode (-i) when stdin is a tty, '+
	                                    'unless an empty esc sequence is provided. If a sequence is multiple characters, they must be entered in order. All characters except the last are echoed to the script. '+
	                                    'Multiple sequences may be defined.')
	parser.add_option('-i', '--immediate', action='store_true', dest='no_buffer', default=False, help='flushes stdout immediately after each cycle, otherwise, default buffering is used. '+
	                                       'Also sets input to raw mode, rather than cbreak mode.')
	parser.add_option('-n', '--extra-newline', action='store_true', dest='extra_newline', default=False, help='provides an extra newline to STDOUT at the end of execution, regardless of the method of termination')
	parser.add_option('-o', '--ignore-eof-ones', action='store_true', dest='ignore_eof_o', default=False, help='when input is exhausted, instead of terminating, provides one values (0xff) until the circuit terminates itself')
	parser.add_option('-v', '--verbose', action='store_true', dest='verbose', default=False, help='enables verbose output; shows the parsed circuitry and input/output for each cycle')
	parser.add_option('-V', '--version', action='callback', callback=version_callback, help="show interpreter's version number and exit")
	parser.add_option('-w', '--without-stdin', action='store_true', dest='without', default=False, help='the program uses the default value (set by -z or -o), instead of reading from STDIN. By itself, implies -z')
	parser.add_option('-z', '--ignore-eof-zeroes', action='store_true', dest='ignore_eof_z', default=False, help='when input is exhausted, instead of terminating, provides zero values (0x00) until the circuit terminates itself')
	opts, args = parser.parse_args()

	Cfg.IGNORE_EOF = opts.ignore_eof_z or opts.ignore_eof_o
	Cfg.NEWLINE = opts.extra_newline
	Cfg.VERBOSE = opts.verbose
	Cfg.WITHOUT_STDIN = opts.without
	Cfg.NO_BUFFER = opts.no_buffer

	if opts.ignore_eof_o:
		Cfg.DEFAULT_VALUE = bytes([255])
	else:
		Cfg.DEFAULT_VALUE = bytes([0])

	esc_seqs_str = []
	if Cfg.NO_BUFFER and stdin.isatty():
		esc_seqs_str = ['\x03', '\x04'] # By default, ^C or ^D will cause exit
	if opts.esc_seqs:
		if '' in opts.esc_seqs:
			esc_seqs_str = []
		esc_seqs_str += [seq for seq in opts.esc_seqs if seq]
	Cfg.ESC_SEQS = tuple(set([seq.encode('utf-8').decode('unicode_escape').encode('utf-8') for seq in esc_seqs_str]))

	if (Cfg.NO_BUFFER and stdin.isatty()) or opts.esc_seqs:
		stderr.write('Escape sequences are: ' + repr(Cfg.ESC_SEQS) + '\n')

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
		elif (not layercomment) and spec[char] == ':':
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
	if Cfg.VERBOSE:
		stderr.write(str(board) + '\n')

	def circuit_gen():
		"""A generator representing the board's state and function"""
		outbits = None
		status = 0
		sleep = 0
		debug = ''
		try:
			while True:
				inbits = yield (status, outbits, sleep, debug)
				status, outbits, sleep, debug = board.run(inbits)
		except KeyboardInterrupt as e:
			if board.debug:
				for msg in sorted(board.debug):
					stderr.write('\n\t\t\t\t\t%s(%d,%d,%d): %s' % msg)
			if Cfg.VERBOSE:
				stderr.write('\n' + str(board))
			stderr.write('\nStack: ')
			if board.stack:
				if VERBOSE or len(board.stack) < 9:
					stderr.write(' '.join(map(lambda v:''.join(map(str, v[::-1])), board.stack[::-1])))
				else:
					stderr.write(' '.join(map(lambda v:''.join(map(str, v[::-1])), board.stack[:-9:-1])))
					stderr.write(' ... ')
					stderr.write(str(len(board.stack)-8))
					stderr.write('more')
			else:
				stderr.write('empty')
			stderr.write('\nAge: ')
			stderr.write(str(board.age))
			if (board.stats):
				stderr.write('\nStats: ')
				for k,v in sorted(board.stats.items()):
					stderr.write('\n%s %s' % (str(v).rjust(24), k))
			stderr.write('\n')

	# Start up the circuit
	circuit = circuit_gen()
	circuit.send(None)

	return circuit, board

def run(circuit, board):
	"""Run the circuit for each input byte"""
	if Cfg.VERBOSE:
		stderr.write('        HGFEDCBA        hgfedcba\n')
	status = 0
	inchar = Cfg.DEFAULT_VALUE
	history = b''
	try:
		while True:
			# Read input, plus eof check
			if not (status & chiplib.Board.READ_HOLD):
				if Cfg.WITHOUT_STDIN:
					inchar = Cfg.DEFAULT_VALUE
				else:
					try:
						if Cfg.NO_BUFFER and stdin.isatty():
							orig_settings = termios.tcgetattr(stdin)
							tty.setraw(stdin)
						inchar = stdin.buffer.read(1)
					finally:
						if Cfg.NO_BUFFER and stdin.isatty():
							termios.tcsetattr(stdin, termios.TCSADRAIN, orig_settings)
					if len(inchar) == 0:
						# EOF
						if Cfg.IGNORE_EOF:
							inchar = Cfg.DEFAULT_VALUE
						else:
							break
					history += inchar
					if history.endswith(Cfg.ESC_SEQS):
						break
			inbin = bin(ord(inchar))[2:]
			inbits = list(map(int, '0'*(8-len(inbin)) + inbin))[::-1]
			if Cfg.VERBOSE:
				if not (status & chiplib.Board.READ_HOLD):
					if 0 <= inchar[0] < 32 or inchar[0] == 127:
						inc = '�'
					else:
						inc = inchar.decode('utf-8', 'replace')
					stderr.write('     %s\t%s  →' % (inc, ''.join(map(str, inbits[::-1]))))
				else:
					stderr.write('                  →')
	
			# Execute a clock cycle
			status, outbits, sleep, debug = circuit.send(inbits)
	
			# Output
			outchar = bytes([int(''.join(map(str, outbits[::-1])), 2)])
			if Cfg.VERBOSE:
				if not (status & chiplib.Board.WRITE_HOLD):
					if 0 <= outchar[0] < 32 or outchar[0] == 127:
						outc = '�'
					else:
						outc = outchar.decode('utf-8', 'replace')
					stderr.write('  %s\t%s' % (outc, ''.join(map(str, outbits[::-1]))))
				else:
					stderr.write('             ')
				if debug:
					for msg in sorted(debug):
						stderr.write('\n\t\t\t\t\t%s(%d,%d,%d): %s' % msg)
				stderr.write('\n')

			if not (status & chiplib.Board.WRITE_HOLD):
				stdout.buffer.write(outchar)
				if Cfg.NO_BUFFER:
					stdout.flush()
	
			# Early termination
			if (status & chiplib.Board.TERMINATE):
				break

			# Sleep
			if (sleep):
				time.sleep(sleep)
		if Cfg.VERBOSE:
			stderr.write('\nAge: ')
			stderr.write(str(board.age))
			if (board.stats):
				stderr.write('\nStats: ')
				for k,v in sorted(board.stats.items()):
					stderr.write('\n%s %s' % (str(v).rjust(24), k))
			stderr.write('\n')
	except StopIteration as e:
		stderr.write('Execution halted\n')
	if Cfg.NEWLINE:
		stdout.buffer.write(b'\n')

if __name__ == '__main__':
	spec = init()
	circuit, board = setup(spec)
	run(circuit, board)
