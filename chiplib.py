#!/usr/bin/python3
#coding=utf-8
#author Derek Anderson
#interpreter v0.1.3

import random
from collections import defaultdict

# Below, plus some padding should be less than window width
COLUMNS = 100

oppositeDir = {
		'n':'s',
		'e':'w',
		's':'n',
		'w':'e',
		'u':'d',
		'd':'u'
	}

###                         ###
#   Start class definitions   #
###                         ###

class Board(object):
	READ_HOLD = 0x1
	WRITE_HOLD = 0x2
	TERMINATE = 0x4

	MAX_POLL_DEPTH = 256
	CUR_POLL_DEPTH = 0

	def __init__(self):
		self.cboard = None
		self.terminals = defaultdict(set)
	def __str__(self):
		if self.initialized():
			out = ''
			# Find out how many frames fit in columns
			n = COLUMNS//(self.w+1)
			n = 1 if n == 0 else n
			# Spread the frames evenly across rows
			n = (self.d+n-1)//n
			n = (self.d+n-1)//n
			for chunk in [self.cboard[n*i:n*(i+1)] for i in range((self.d+n-1)//n)]:
				lines = [' ║']*(self.h+2)
				lines[0] = ' ╔' + '╦'.join(['═'*self.w]*len(chunk)) + '╗'
				for layer in chunk:
					for j in range(self.h):
						lines[j+1] += ''.join(map(lambda elem: str(elem), layer[j])) + '║'
				lines[-1] = ' ╚' + '╩'.join(['═'*self.w]*len(chunk)) + '╝'
				out += '\n'.join(lines) + '\n'
			return out
		else:
			return ''
	def __repr__(self):
		if self.initialized():
			return '<Board %dx%dx%d>' % (self.w, self.h, self.d)
		else:
			return '<Board Uninitialized>'

	def initialize(self, cboard):
		self.cboard = cboard
		self.d = len(cboard)
		self.h = len(cboard[0])
		self.w = len(cboard[0][0])
		self.inbits = [0]*8
		self.outbits = [0]*8
		self.statuscode = 0
		self.stackctl = {'w':set(), 'r':set()}
		self.stack = []
		self.age = 0
		self.debug = ''

		def processStackWrite():
			if self.getStackControl('w'):
				# push current stack value to second position
				self.stack.append([0]*8)
		def processStackRead():
			if self.getStackControl('r'):
				# remove current value to bring up the next
				self.stack.pop()

		self.registerInternal(processStackWrite, 11)
		self.registerInternal(processStackRead, 99)

	def initialized(self):
		return self.cboard is not None

	def registerInternal(self, element, rank):
		self.terminals[rank].add(element)

	def getElement(self, x, y, z):
		if 0 <= x < self.w and\
		   0 <= y < self.h and\
		   0 <= z < self.d:
			return self.cboard[z][y][x]
		else:
			return None

	def run(self, inbits):
		self.inbits = inbits
		self.outbits = [0]*8
		self.statuscode = 0
		self.stackctl['w'].clear()
		self.stackctl['r'].clear()
		self.age += 1
		self.debug = ''

		if not self.stack:
			# avoid an empty stack by providing a zero value
			self.stack.append([0]*8)

		for rank in sorted(self.terminals.keys()):
			for element in self.terminals[rank]:
				if hasattr(element, 'pollInternal'):
					element.pollInternal()
				else:
					# we have a special task function, not an actual element
					task = element
					task()

		return (self.statuscode, self.outbits, self.debug)

	def readBit(self, index):
		return self.inbits[index]
	def writeBit(self, index, value):
		self.outbits[index] |= value

	def addStatus(self, statuscode):
		self.statuscode |= statuscode
	def addDebug(self, debugMsg):
		self.debug += str(debugMsg)

	def checkStatus(self, statuscode):
		return self.statuscode & statuscode

	def setStackControl(self, control, controlFlavor, controlValue):
		if controlValue == 1:
			self.stackctl[controlFlavor].add(control)
		elif controlValue == 0:
			self.stackctl[controlFlavor].discard(control)
		else:
			assert 1 == 0, "'%d' is not a valid stack control value" % (controlValue)
	def getStackControl(self, controlFlavor):
		return 1 if self.stackctl[controlFlavor] else 0

	def readStackBit(self, index):
		assert self.stack, "Tried to read from an empty stack"
		return self.stack[-1][index]
	def writeStackBit(self, index, value):
		assert self.stack, "Tried to write to an empty stack"
		self.stack[-1][index] |= value

class Element(object):
	def __init__(self, board, x, y, z, lexeme):
		self.board = board
		self.x = x
		self.y = y
		self.z = z
		self.lexeme = lexeme
	def __str__(self):
		return self.lexeme
	def __repr__(self):
		return self.__class__.__name__ + '(' + self.__str__() + ')'

	def getNeighbor(self, dir):
		if dir == 'n':
			if self.y <= 0:
				return None
			else:
				return self.board.getElement(self.x, self.y-1, self.z)
		elif dir == 's':
			if self.y+1 >= self.board.h:
				return None
			else:
				return self.board.getElement(self.x, self.y+1, self.z)
		elif dir == 'w':
			if self.x <= 0:
				return None
			else:
				return self.board.getElement(self.x-1, self.y, self.z)
		elif dir == 'e':
			if self.x+1 >= self.board.w:
				return None
			else:
				return self.board.getElement(self.x+1, self.y, self.z)
		elif dir == 'u':
			if self.z <= 0:
				return None
			else:
				return self.board.getElement(self.x, self.y, self.z-1)
		elif dir == 'd':
			if self.z+1 >= self.board.d:
				return None
			else:
				return self.board.getElement(self.x, self.y, self.z+1)
		else:
			assert 1 == 0, "'%s' is not a valid direction" % (dir)

	def poll(self, side):
		"""Called by neighboring elements to read a value. Must give 0
		   for low, or 1 for high. Must return a value for all sides
		   'n', 's', 'w', 'e', 'u', and 'd'."""
		return 0
	def pollInternal(self):
		"""Must be registered to the owning Board if implemented. Used
		   by elements that need to run every cycle, but may not be
		   polled conventionally."""
		pass
	def pollNeighbor(self, dir):
		"""Should not be overridden in most circumstances. Used to poll
		   a neighboring element. Enforces a soft recursion limit, and
		   handles board edges."""
		neighbor = self.getNeighbor(dir)
		if neighbor is not None:
			if Board.CUR_POLL_DEPTH < Board.MAX_POLL_DEPTH:
				Board.CUR_POLL_DEPTH += 1
				value = neighbor.poll(oppositeDir[dir])
				Board.CUR_POLL_DEPTH -= 1
				return value
			else:
				# Soft recursion limit reached
				return 0
		else:
			# Edge of board
			return 0

	def neighborType(self, dir):
		return type(self.getNeighbor(dir))

###                       ###
#   Begin Element Classes   #
###                       ###

class Adder(Element):
	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)

	@staticmethod
	def getFlavor(lexeme):
		if lexeme in '#':
			return 'ew', '#'
		elif lexeme in '@':
			return 'we', '@'
		else:
			assert 1 == 0, "'%s' is not a valid lexeme for a %s element" % (lexeme, self.__class__.__name__)

	def poll(self, side):
		if side == self.flavor[0]:
			return self.pollNeighbor('n') ^ self.pollNeighbor(self.flavor[1])
		elif side == 's':
			return self.pollNeighbor('n') and self.pollNeighbor(self.flavor[1])
		else:
			return 0

class And(Element):
	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)

	@staticmethod
	def getFlavor(lexeme):
		if lexeme in ']':
			return 'ew', ']'
		elif lexeme in '[':
			return 'we', '['
		else:
			assert 1 == 0, "'%s' is not a valid lexeme for a %s element" % (lexeme, self.__class__.__name__)

	def poll(self, side):
		if side == self.flavor[0]:
			a = self.pollNeighbor('n') or\
			    self.pollNeighbor('s')
			return a and self.pollNeighbor(self.flavor[1])
		elif side == 'n':
			return self.pollNeighbor('s')
		elif side == 's':
			return self.pollNeighbor('n')
		else:
			return 0

class Cache(Element):
	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, lexeme)
		self.ages = {'n':0, 's':0, 'e':0, 'w':0}
		self.values = {'n':0, 's':0, 'e':0, 'w':0}

	# Make second flavor 'k' that only polls the opposite neighbor of each side?

	def poll(self, side):
		if side in self.values.keys():
			if self.ages[side] != self.board.age:
				self.ages[side] = self.board.age
				self.values[side] = 0;
				for dir in self.values.keys():
					if dir == side:
						continue
					self.values[side] = self.values[side] or self.pollNeighbor(dir)
			return self.values[side]
		else:
			return 0

class Control(Element):
	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, lexeme)
		board.registerInternal(self, 80)

	def pollInternal(self):
		if (   (self.lexeme == 'T' and self.board.checkStatus(Board.WRITE_HOLD) and self.board.checkStatus(Board.TERMINATE))
		    or (self.lexeme == 't' and self.board.checkStatus(Board.TERMINATE))
		    or (self.lexeme == 'S' and self.board.checkStatus(Board.WRITE_HOLD))
		    or (self.lexeme == 's' and self.board.checkStatus(Board.READ_HOLD))):
			# value already set, no use to poll anything
			pass
		else:
			value = self.pollNeighbor('n') or\
			        self.pollNeighbor('s') or\
			        self.pollNeighbor('w') or\
			        self.pollNeighbor('e')
			if value:
				if self.lexeme == 'T':
					self.board.addStatus(Board.WRITE_HOLD | Board.TERMINATE)
				elif self.lexeme == 't':
					self.board.addStatus(Board.TERMINATE)
				elif self.lexeme == 'S':
					self.board.addStatus(Board.WRITE_HOLD)
				elif self.lexeme == 's':
					self.board.addStatus(Board.READ_HOLD)

class Debug(Element):
	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, lexeme)
		board.registerInternal(self, 90)

	def pollInternal(self):
		value = self.pollNeighbor('n') or\
		        self.pollNeighbor('s') or\
		        self.pollNeighbor('w') or\
		        self.pollNeighbor('e')
		self.board.addDebug('\n\t\t\t\t\t%s(%d,%d,%d): %s' % (self.lexeme, self.z, self.y, self.x, value))

class Delay(Element):
	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)
		self.age = 0
		self.currValue = 0
		self.nextValue = 0
		board.registerInternal(self, 80)

	@staticmethod
	def getFlavor(lexeme):
		if lexeme in 'Z':
			return 'ew', 'Z'
		elif lexeme in 'z':
			return 'we', 'z'
		else:
			assert 1 == 0, "'%s' is not a valid lexeme for a %s element" % (lexeme, self.__class__.__name__)

	def pollInternal(self):
		if self.age != self.board.age:
			self.currValue = self.nextValue
			self.age = self.board.age
			self.nextValue = self.pollNeighbor('n') or self.pollNeighbor(self.flavor[1])

	def poll(self, side):
		if side in ['s', self.flavor[0]]:
			if self.age == self.board.age:
				return self.currValue
			else:
				return self.nextValue
		else:
			return 0

class Diode(Element):
	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, ' ')

	@staticmethod
	def getFlavor(lexeme):
		if lexeme in '»':
			return 'ew', '»'
		elif lexeme in '«':
			return 'we', '«'
		else:
			assert 1 == 0, "'%s' is not a valid lexeme for a %s element" % (lexeme, self.__class__.__name__)

	def poll(self, side):
		if side == self.flavor[0]:
			return self.pollNeighbor(self.flavor[1])
		else:
			return 0

class Empty(Element):
	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, ' ')

class InBit(Element):
	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, lexeme)
		self.index = 'ABCDEFGH'.index(lexeme)

	def poll(self, side):
		if side in 'nswe':
			return self.board.readBit(self.index)
		else:
			return 0

class Memory(Element):
	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)
		self.currValue = 0
		board.registerInternal(self, 60)

	@staticmethod
	def getFlavor(lexeme):
		if lexeme in 'M':
			return 'ew', 'M'
		elif lexeme in 'm':
			return 'we', 'm'
		else:
			assert 1 == 0, "'%s' is not a valid lexeme for a %s element" % (lexeme, self.__class__.__name__)

	def pollInternal(self):
		if self.pollNeighbor('n') or self.pollNeighbor('s'):
			self.currValue = self.pollNeighbor(self.flavor[1])

	def poll(self, side):
		if side == self.flavor[0]:
			self.pollInternal()
			return self.currValue
		elif side == 'n':
			return self.pollNeighbor('s')
		elif side == 's':
			return self.pollNeighbor('n')
		else:
			return 0

class Not(Element):
	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)

	@staticmethod
	def getFlavor(lexeme):
		if lexeme in '⌐~':
			return 'ew', '⌐'
		elif lexeme in '¬÷':
			return 'we', '¬'
		else:
			assert 1 == 0, "'%s' is not a valid lexeme for a %s element" % (lexeme, self.__class__.__name__)

	def poll(self, side):
		if side == self.flavor[0]:
			return 1 - self.pollNeighbor(self.flavor[1])
		else:
			return 0

class Or(Element):
	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)

	@staticmethod
	def getFlavor(lexeme):
		if lexeme in ')':
			return 'ew', ')'
		elif lexeme in '(':
			return 'we', '('
		else:
			assert 1 == 0, "'%s' is not a valid lexeme for a %s element" % (lexeme, self.__class__.__name__)

	def poll(self, side):
		if side == self.flavor[0]:
			a = self.pollNeighbor('n') or\
			    self.pollNeighbor('s')
			return a or self.pollNeighbor(self.flavor[1])
		elif side == 'n':
			return self.pollNeighbor('s')
		elif side == 's':
			return self.pollNeighbor('n')
		else:
			return 0

class OutBit(Element):
	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, lexeme)
		self.index = 'abcdefgh'.index(lexeme)
		board.registerInternal(self, 90)

	def pollInternal(self):
		if self.board.checkStatus(Board.WRITE_HOLD):
			# Optimization - do not perform OutBit polls when WRITE_HOLD
			return
		value = self.pollNeighbor('n') or\
		        self.pollNeighbor('s') or\
		        self.pollNeighbor('w') or\
		        self.pollNeighbor('e')
		self.board.writeBit(self.index, value)

class Pin(Element):
	def __init__(self, board, x, y, z, lexeme):
		lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)

	@staticmethod
	def getFlavor(lexeme):
		if lexeme in 'Oo':
			return lexeme
		else:
			assert 1 == 0, "'%s' is not a valid lexeme for a %s element" % (lexeme, self.__class__.__name__)

	def poll(self, side):
		# Pins connect to non-pins always, and pins only when:
		# - Same lexeme and different layer, or
		# - Same layer and different lexeme
		# We check on outgoing pin polls, and so assume all incoming polls are good
		value = 0
		for s in 'ud':
			if value == 1:
				break
			if s != side:
				if self.neighborType(s) != self.__class__ or self.getNeighbor(s).lexeme == self.lexeme:
					value = value or self.pollNeighbor(s)
		for s in 'nswe':
			if value == 1:
				break
			if s != side:
				if self.neighborType(s) != self.__class__ or self.getNeighbor(s).lexeme != self.lexeme:
					value = value or self.pollNeighbor(s)
		return value

class Random(Element):
	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, '?')
		self.age = 0
		self.value = 0

	def poll(self, side):
		if side in 'nswe':
			if self.age != self.board.age:
				self.value = random.choice([0, 1])
				self.age = self.board.age
			return self.value
		else:
			return 0

class Source(Element):
	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, '*')

	def poll(self, side):
		if side in 'nswe':
			return 1
		else:
			return 0

class StackBit(Element):
	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, lexeme)
		self.index = '01234567'.index(lexeme)
		board.registerInternal(self, 20)

	def pollInternal(self):
		if self.board.getStackControl('w'):
			value = (0 if self.neighborType('n') == self.__class__ else self.pollNeighbor('n')) or\
			        (0 if self.neighborType('s') == self.__class__ else self.pollNeighbor('s')) or\
			        (0 if self.neighborType('w') == self.__class__ else self.pollNeighbor('w')) or\
			        (0 if self.neighborType('e') == self.__class__ else self.pollNeighbor('e'))
			self.board.writeStackBit(self.index, value)

	def poll(self, side):
		if side in 'nswe' and self.board.getStackControl('r'):
			return self.board.readStackBit(self.index)
		else:
			return 0

class StackControl(Element):
	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)
		board.registerInternal(self, 10)

	@staticmethod
	def getFlavor(lexeme):
		if lexeme in '9':
			return 'w', '9'
		elif lexeme in '8':
			return 'r', '8'
		else:
			assert 1 == 0, "'%s' is not a valid lexeme for a %s element" % (lexeme, self.__class__.__name__)

	def pollInternal(self):
		value = self.pollNeighbor('n') or\
		        self.pollNeighbor('s') or\
		        self.pollNeighbor('w') or\
		        self.pollNeighbor('e')
		self.board.setStackControl(self, self.flavor, value)

class Switch(Element):
	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)

	@staticmethod
	def getFlavor(lexeme):
		if lexeme in '/':
			return 1, '/'
		elif lexeme in '\\':
			return 0, '\\'
		else:
			assert 1 == 0, "'%s' is not a valid lexeme for a %s element" % (lexeme, self.__class__.__name__)

	def poll(self, side):
		if side == 'n':
			return self.pollNeighbor('s')
		elif side == 's':
			return self.pollNeighbor('n')
		elif side == 'w':
			a = self.pollNeighbor('n') or\
			    self.pollNeighbor('s')
			if a == self.flavor:
				return self.pollNeighbor('e')
			else:
				return 0
		elif side == 'e':
			a = self.pollNeighbor('n') or\
			    self.pollNeighbor('s')
			if a == self.flavor:
				return self.pollNeighbor('w')
			else:
				return 0
		else:
			return 0

class Wire(Element):
	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)

	@staticmethod
	def getFlavor(lexeme):
		if lexeme in '+┼':
			return 'nswe', '┼'
		elif lexeme in '|│':
			return 'ns', '│'
		elif lexeme in '-─':
			return 'ew', '─'
		elif lexeme in '^┴':
			return 'nwe', '┴'
		elif lexeme in 'v┬':
			return 'swe', '┬'
		elif lexeme in '>├':
			return 'nse', '├'
		elif lexeme in '<┤':
			return 'nsw', '┤'
		elif lexeme in '`└':
			return 'ne', '└'
		elif lexeme in '\'┘':
			return 'nw', '┘'
		elif lexeme in ',┌':
			return 'se', '┌'
		elif lexeme in '.┐':
			return 'sw', '┐'
		else:
			assert 1 == 0, "'%s' is not a valid lexeme for a %s element" % (lexeme, self.__class__.__name__)

	def poll(self, side):
		if side in self.flavor:
			value = 0
			for dir in self.flavor:
				if dir != side:
					value = value or self.pollNeighbor(dir)
				if value:
					break
			return value
		else:
			return 0

class WireCross(Element):
	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, '×')

	def poll(self, side):
		if side == 'n':
			return self.pollNeighbor('s')
		elif side == 's':
			return self.pollNeighbor('n')
		elif side == 'w':
			return self.pollNeighbor('e')
		elif side == 'e':
			return self.pollNeighbor('w')
		else:
			return 0

class Xor(Element):
	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)

	@staticmethod
	def getFlavor(lexeme):
		if lexeme in '}':
			return 'ew', '}'
		elif lexeme in '{':
			return 'we', '{'
		else:
			assert 1 == 0, "'%s' is not a valid lexeme for a %s element" % (lexeme, self.__class__.__name__)

	def poll(self, side):
		if side == self.flavor[0]:
			a = self.pollNeighbor('n') or\
			    self.pollNeighbor('s')
			return a ^ self.pollNeighbor(self.flavor[1])
		elif side == 'n':
			return self.pollNeighbor('s')
		elif side == 's':
			return self.pollNeighbor('n')
		else:
			return 0

###                     ###
#   End Element classes   #
###                     ###

lexmap = {
		'@#': Adder,
		'[]': And,
		'K': Cache,
		'TtSs': Control,
		'X': Debug,
		'Zz': Delay,
		'«»': Diode,
		' ': Empty,
		'ABCDEFGH': InBit,
		'Mm': Memory,
		'⌐¬÷~': Not,
		'()': Or,
		'abcdefgh': OutBit,
		'Oo': Pin,
		'?': Random,
		'*': Source,
		'01234567': StackBit,
		'89': StackControl,
		'\\/': Switch,
		'─│┌┐└┘├┤┬┴┼+|-^v><,.`\'': Wire,
		'×x': WireCross,
		'{}': Xor
	}

def getElementType(lexeme):
	for lexes,etype in lexmap.items():
		if lexeme in lexes:
			return etype
	else:
		assert 1 == 0, "'%s' is not a valid lexeme" % (lexeme)
		return Empty

if __name__ == '__main__':
	print('This file cannot be executed directly. Please use the chip interpreter instead.')

