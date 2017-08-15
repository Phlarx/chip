#!/usr/bin/python3 -bb
#coding=utf-8
#author Derek Anderson
#interpreter v0.1.5

VERSION = '0.1.5'

from sys import argv, stdin, stdout, stderr, exit
from getopt import getopt, GetoptError
from argparse import ArgumentParser, RawDescriptionHelpFormatter

import random, time, termios, tty
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
	CUTOFF_BYTES=-1,
	ESC_SEQS=tuple(),
	GENERATOR=None,
	IGNORE_EOF=False,
	NEWLINE=False,
	NO_BUFFER=False,
	VERBOSE=False,
	WITHOUT_STDIN=False
)

def prepareGenerator(template):
	def inputGenerator():
		age = 0
		while(True):
			value = list(template.upper())

			if value[0] == 'I':
				value[0] = '0123456789ABCDEF'[(age >> 4) & 15]
			elif value[0] == 'J':
				value[0] = '0123456789ABCDEF'[~((age >> 4) & 15)]
			elif value[0] == 'K':
				value[0] = random.choice('0123456789ABCDEF')

			if value[1] == 'I':
				value[1] = '0123456789ABCDEF'[age & 15]
			elif value[1] == 'J':
				value[1] = '0123456789ABCDEF'[~(age & 15)]
			elif value[1] == 'K':
				value[1] = random.choice('0123456789ABCDEF')

			yield bytes([int(''.join(value), 16)])
			age = (age + 1) % 256
	return inputGenerator()

def init():
	"""Perform initialization tasks"""
	justify = max(len(cls.__name__) for cls in chiplib.lexmap_r.keys()) + 2
	valid_elements = 'supported elements:\n  '+'Type'.ljust(justify)+'Lexemes\n'
	for cls, lexes in sorted([(cls.__name__, lexes) for cls, lexes in chiplib.lexmap_r.items()]):
		valid_elements += '  %s%s\n' % (cls.ljust(justify), ' '.join(sorted(lexes)))

	parser = ArgumentParser(usage='%(prog)s [options] <chipspec>', conflict_handler='resolve',
	                        formatter_class=RawDescriptionHelpFormatter, epilog=valid_elements)
	# Positional args
	parser.add_argument('chipspec', action='store', type=str, nargs='?', metavar='chipspec', help='A Chip specification file.')
	# Optional args
	parser.add_argument('-c', '--cutoff', action='store', dest='cutoff_bytes', default=-1, type=int, metavar='N', help='Stop '+
	                                      'processing and halt after N bytes; applies to both stdin and generated bytes.')
	parser.add_argument('-e', '--escape', action='append', dest='esc_seqs', metavar='SEQ', help='Use these characters as escape '+
	                                      'sequences for input. A default of ^C and ^D are included in immediate mode (-i) when '+
	                                      'stdin is a tty, unless an empty esc sequence is provided. If a sequence is multiple '+
	                                      'characters, they must be entered in order. All characters except the last are echoed to '+
	                                      'the script. Multiple sequences may be defined.')
	parser.add_argument('-g', '--generate', action='store', dest='generator', default='', type=str, metavar='XX', help='When input '+
	                                        'is exhausted, instead of terminating, generate values defined by XX. XX is two digits '+
	                                        "of base 16, or special characters 'I', 'J', or 'K'. 'I' means count up, 'J' means "+
	                                        "count down, 'K' means random value. Place values are respected, so 'I5' means that the "+
	                                        'low four bits are always 0101, and the upper four bits will increment every 16 cycles. '+
	                                        'Any counting starts at the end of stdin. Case insensitive.')
	parser.add_argument('-h', '--help', action='help', help='Show this help message and exit.')
	parser.add_argument('-i', '--immediate', action='store_true', dest='no_buffer', default=False, help='Flushes stdout immediately '+
	                                         'after each cycle, otherwise, default buffering is used. Also sets input to raw mode, '+
	                                         'rather than cbreak mode.')
	parser.add_argument('-n', '--extra-newline', action='store_true', dest='extra_newline', default=False, help='Provides an extra '+
	                                             'newline to stdout at the end of execution regardless of the method of termination.')
	parser.add_argument('-o', '--generate-one', action='store_const', dest='generator', const='FF', help='When input is exhausted, '+
	                                            'instead of terminating, generate one values (0xff) until the circuit terminates '+
	                                            'itself. Equivalent to --generate=FF.')
	parser.add_argument('-v', '--verbose', action='count', dest='verbose', default=0, help='Enables verbose output; effect is '+
	                                       'cumulative. Level 1 shows input/output for each cycle. Level 2 adds the parsed '+
	                                       'circuitry and statistics. Level 3 shows a heatmap (using ANSI colors).')
	parser.add_argument('-V', '--version', action='version', version=('Chip interpreter v'+VERSION), help="Show interpreter's "+
	                                       'version number and exit.')
	parser.add_argument('-w', '--without-stdin', action='store_true', dest='without', default=False, help='The program uses the '+
	                                             'default value (set by --generate), instead of reading from STDIN. By itself, '+
	                                             'implies --generate=00.')
	parser.add_argument('-z', '--generate-zero', action='store_const', dest='generator', const='00', help='When input is exhausted, '+
	                                             'instead of terminating, generate zero values (0x00) until the circuit terminates '+
	                                             'itself. Equivalent to --generate=00.')
	args = parser.parse_args()

	if args.without and not args.generator:
		args.generator = '00'

	Cfg.CUTOFF_BYTES = args.cutoff_bytes
	Cfg.IGNORE_EOF = bool(args.generator)
	Cfg.GENERATOR = prepareGenerator(args.generator)
	Cfg.NEWLINE = args.extra_newline
	Cfg.NO_BUFFER = args.no_buffer
	Cfg.VERBOSE = args.verbose
	Cfg.WITHOUT_STDIN = args.without

	esc_seqs_str = []
	if Cfg.NO_BUFFER and stdin.isatty():
		esc_seqs_str = ['\x03', '\x04'] # By default, ^C or ^D will cause exit
	if args.esc_seqs:
		if '' in args.esc_seqs:
			esc_seqs_str = []
		esc_seqs_str += [seq for seq in args.esc_seqs if seq]
	Cfg.ESC_SEQS = tuple(set([seq.encode('utf-8').decode('unicode_escape').encode('utf-8') for seq in esc_seqs_str]))

	if (Cfg.NO_BUFFER and stdin.isatty()) or args.esc_seqs:
		stderr.write('Escape sequences are: ' + repr(Cfg.ESC_SEQS) + '\n')

	if args.chipspec:
		with open(args.chipspec, 'r') as f:
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
	if Cfg.VERBOSE > 1:
		stderr.write(str(board) + '\n')

	def circuit_gen():
		"""A generator representing the board's state and function"""
		outbits = None
		status = 0
		sleep = 0
		debug = ''
		jump = None
		try:
			while True:
				inbits = yield (status, outbits, sleep, debug, jump)
				status, outbits, sleep, debug, jump = board.run(inbits)
		except KeyboardInterrupt as e:
			if board.debug:
				for msg in sorted(board.debug):
					stderr.write('\n\t\t\t\t\t%s(%d,%d,%d): %s' % msg)
			if Cfg.VERBOSE > 2:
				stderr.write('\n' + board.heatmap())
			stderr.write('\nStack: ')
			if board.stack:
				if Cfg.VERBOSE > 1 or len(board.stack) < 9:
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
			#raise e # Uncomment this for a stack trace. Usually *very* long.

	# Start up the circuit
	circuit = circuit_gen()
	circuit.send(None)

	return circuit, board

def run(circuit, board):
	"""Run the circuit for each input byte"""
	if Cfg.VERBOSE > 0:
		stderr.write('        HGFEDCBA        hgfedcba\n')
	status = 0
	total_bytes = 0
	inchar = bytes([254])
	history = b''
	index = 0
	try:
		while True:
			# Read input, plus eof check
			if not (status & chiplib.Board.READ_HOLD):
				if total_bytes >= Cfg.CUTOFF_BYTES > 0:
					# we're done here
					break
				if index < len(history):
					inchar = bytes([history[index]]) # need to bytes, otherwise we get an int
				else:
					if Cfg.WITHOUT_STDIN:
						inchar = next(Cfg.GENERATOR)
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
							# EOF (optimization: switch to without stdin mode for future)
							if Cfg.IGNORE_EOF:
								inchar = next(Cfg.GENERATOR)
								Cfg.WITHOUT_STDIN = True
							else:
								break
					history += inchar
					if history.endswith(Cfg.ESC_SEQS):
						break
				index += 1
				total_bytes += 1
			inbin = bin(ord(inchar))[2:]
			inbits = list(map(int, '0'*(8-len(inbin)) + inbin))[::-1]
			if Cfg.VERBOSE > 0:
				if not (status & chiplib.Board.READ_HOLD):
					if 0 <= inchar[0] < 32 or inchar[0] == 127:
						inc = '�'
					else:
						inc = inchar.decode('utf-8', 'replace')
					stderr.write('     %s\t%s  →' % (inc, ''.join(map(str, inbits[::-1]))))
				else:
					stderr.write('                  →')
	
			# Execute a clock cycle
			status, outbits, sleep, debug, jump = circuit.send(inbits)
	
			# Output
			outchar = bytes([int(''.join(map(str, outbits[::-1])), 2)])
			if Cfg.VERBOSE > 0:
				if not (status & chiplib.Board.WRITE_HOLD):
					if 0 <= outchar[0] < 32 or outchar[0] == 127:
						outc = '�'
					else:
						outc = outchar.decode('utf-8', 'replace')
					stderr.write('  %s\t%s' % (outc, ''.join(map(str, outbits[::-1]))))
				else:
					stderr.write('             ')
				if Cfg.VERBOSE > 1:
					if debug:
						for msg in sorted(debug):
							stderr.write('\n\t\t\t\t\t%s(%d,%d,%d): %s' % msg)
					if board.stack:
						stderr.write('\n\t\t\t\t\tStack: ')
						if len(board.stack) < 9:
							stderr.write(' '.join(map(lambda v:''.join(map(str, v[::-1])), board.stack[::-1])))
						else:
							stderr.write(' '.join(map(lambda v:''.join(map(str, v[::-1])), board.stack[:-9:-1])))
							stderr.write(' ... ')
							stderr.write(str(len(board.stack)-8))
							stderr.write('more')
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

			# Jump
			if (jump is not None):
				if jump >= 0:
					index = jump
				else:
					index += jump

		if Cfg.VERBOSE > 1:
			if Cfg.VERBOSE > 2:
				stderr.write('\n')
				stderr.write(board.heatmap())
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
