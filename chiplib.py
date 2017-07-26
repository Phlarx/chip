#!/usr/bin/python3 -bb
#coding=utf-8
#author Derek Anderson
#interpreter v0.1.5

import random, subprocess, sys
from collections import defaultdict

# Determine window width
if sys.version_info[1] >= 3: # Python 3.3+
	import shutil
	_terminal_size = shutil.get_terminal_size((80,20))
	COLUMNS = int(_terminal_size.columns)
else:
	COLUMNS = 80

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
		self.terminals = {cls:set() for cls in PRIORITYLIST}
	def __str__(self):
		if self.initialized():
			out = ''
			# Find out how many frames fit in columns
			n = (COLUMNS-2)//(self.w+1)
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
		self.sleep = 0
		self.statuscode = 0
		self.stackctl = {'w':set(), 'r':set()}
		self.stack = []
		self.stackheadr = None
		self.stackheadw = None
		self.age = 0
		self.debug = []
		self.stats = defaultdict(int)
		self.alerts = set()

		def prepareStack():
			if self.stack:
				# Peek at stack to read
				self.stackheadr = self.stack[-1]
			else:
				# Produce zeroes to read if the stack is empty
				self.stackheadr = [0]*8
			# Create write head unconditionally
			self.stackheadw = [0]*8
		def finalizeStack():
			if self.getStackControl('r') and self.stack:
				# If we were reading, not only peeking, actually pop the stack now
				self.stack.pop()
			if self.getStackControl('w'):
				# If we were writing, commit the write head
				self.stack.append(self.stackheadw)

		self.registerInternal(prepareStack, DummyPrepare)
		self.registerInternal(finalizeStack, DummyFinalize)

	def initialized(self):
		return self.cboard is not None

	def registerInternal(self, element, cls=None):
		if cls is None:
			cls = type(element)
		self.terminals[cls].add(element)

	def getElement(self, x, y, z):
		if 0 <= x < self.w and\
		   0 <= y < self.h and\
		   0 <= z < self.d:
			return self.cboard[z][y][x]
		else:
			return None

	def run(self, inbits):
		self.debug = []
		self.inbits = inbits
		self.outbits = [0]*8
		self.sleep = 0
		self.statuscode = 0
		self.stackctl['w'].clear()
		self.stackctl['r'].clear()
		self.stackheadr = None
		self.stackheadw = None

		self.age += 1

		for cls in PRIORITYLIST:
			for element in self.terminals[cls]:
				element()

		return (self.statuscode, self.outbits, self.sleep, self.debug)

	def readBit(self, index):
		return self.inbits[index]
	def writeBit(self, index, value):
		self.outbits[index] |= value

	def addStatus(self, statuscode):
		self.statuscode |= statuscode
	def addDebug(self, lexeme, z, y, x, msg):
		self.debug.append((lexeme, z, y, x, msg))
	def addSleep(self, sleepduration):
		self.sleep += sleepduration

	def checkStatus(self, statuscode):
		return self.statuscode & statuscode

	def setStackControl(self, control, controlFlavor, controlValue):
		"""The two stack controls -- read and write -- are each lists.
		   When the control is set, the setting element is added to
		   the list, when cleared it is removed. If the list has any
		   values, its control is considered active."""
		if controlValue == 1:
			self.stackctl[controlFlavor].add(control)
		elif controlValue == 0:
			self.stackctl[controlFlavor].discard(control)
		else:
			assert 1 == 0, "'%d' is not a valid stack control value" % (controlValue)
	def getStackControl(self, controlFlavor):
		return 1 if self.stackctl[controlFlavor] else 0

	def readStackBit(self, index):
		return self.stackheadr[index]
	def writeStackBit(self, index, value):
		self.stackheadw[index] |= value

class Element(object):
	lexemes = {}

	def __init__(self, board, x, y, z, lexeme):
		self.board = board
		self.x = x
		self.y = y
		self.z = z
		self.lexeme = lexeme
		self.calls = 0
	def __str__(self):
		return self.lexeme
	def __repr__(self):
		return self.__class__.__name__ + '(' + self.__str__() + ')'
	def __call__(self):
		#self.addDebug('Performing internal poll')
		retval = self.pollInternal()
		self.calls += 1
		self.board.stats['poll.internal'] += 1
		if 'overflow' in self.board.alerts:
			self.addDebug('Stack overflow started here')
			self.board.alerts.discard('overflow')
		return retval

	@classmethod
	def getValidLexemes(cls):
		"""This can be overridden, but the preferred method is to
		   define the variable lexemes to the proper value.
		   Lexemes can be any iterable for this method to work."""
		return frozenset(cls.lexemes)

	def getNeighbor(self, dir):
		"""Finds the next neighbor in any of the directions 'u', 'd',
		   'n', 'w', 's', or 'e'. Not recommended to override."""
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
			raise ValueError("'%s' is not a valid direction" % (dir))

	def poll(self, side):
		"""Called by neighboring elements to read a value. Must give 0
		   for low, 1 for high, or None for no connection. Must handle
		   side values 'n', 's', 'w', 'e', 'u', and 'd'."""
		return None
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
		self.board.stats['poll.neighbor'] += 1
		if neighbor is not None:
			if Board.CUR_POLL_DEPTH < Board.MAX_POLL_DEPTH:
				Board.CUR_POLL_DEPTH += 1
				value = neighbor.poll(oppositeDir[dir])
				if value is None:
					value = 0
				else:
					neighbor.calls += 1
				Board.CUR_POLL_DEPTH -= 1
				return value
			else:
				# Soft recursion limit reached
				self.board.stats['poll.overflow'] += 1
				self.addDebug('Giving up due to stack overflow')
				self.board.alerts.add('overflow')
				return 0
		else:
			# Edge of board
			return 0

	def neighborType(self, dir):
		return type(self.getNeighbor(dir))

	def addDebug(self, msg):
		self.board.addDebug(self.lexeme, self.z, self.y, self.x, msg)

###                       ###
#   Begin Element Classes   #
###                       ###

class Adder(Element):
	lexemes = {'#':('ew','#'), '@':('we','@')}

	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)

	@classmethod
	def getFlavor(cls, lexeme):
		try:
			return cls.lexemes[lexeme]
		except:
			raise KeyError("'%s' is not a valid lexeme for a %s element" % (lexeme, cls.__name__))

	def poll(self, side):
		if side == self.flavor[0]:
			return self.pollNeighbor('n') ^ self.pollNeighbor(self.flavor[1])
		elif side == 's':
			return self.pollNeighbor('n') and self.pollNeighbor(self.flavor[1])
		else:
			return None

class And(Element):
	lexemes = {']':('ew',']'), '[':('we','[')}

	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)

	@classmethod
	def getFlavor(cls, lexeme):
		try:
			return cls.lexemes[lexeme]
		except:
			raise KeyError("'%s' is not a valid lexeme for a %s element" % (lexeme, cls.__name__))

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
			return None

class Cache(Element):
	lexemes = 'K'

	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, lexeme)
		self.ages = {'n':0, 's':0, 'e':0, 'w':0}
		self.outValues = {'n':0, 's':0, 'e':0, 'w':0}

	# Make second flavor 'k' that only polls the opposite neighbor of each side?

	def poll(self, side):
		if side in self.outValues.keys():
			if self.ages[side] != self.board.age:
				self.ages[side] = self.board.age
				self.outValues[side] = 0;
				for dir in self.outValues.keys():
					if dir == side:
						continue
					self.outValues[side] = self.outValues[side] or self.pollNeighbor(dir)
				self.board.stats['cache.miss'] += 1
			else:
				self.board.stats['cache.hit'] += 1
			return self.outValues[side]
		else:
			return None

class Control(Element):
	lexemes = 'TtSs'

	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, lexeme)
		board.registerInternal(self)

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
	lexemes = 'X'

	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, self.lexemes[0])
		board.registerInternal(self)

	def pollInternal(self):
		value = self.pollNeighbor('n') or\
		        self.pollNeighbor('s') or\
		        self.pollNeighbor('w') or\
		        self.pollNeighbor('e')
		self.addDebug(value)

class Delay(Element):
	lexemes = {'Z':('ew','Z'), 'z':('we','z')}

	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)
		self.age = 0
		self.currValue = 0
		self.nextValue = 0
		board.registerInternal(self)

	@classmethod
	def getFlavor(cls, lexeme):
		try:
			return cls.lexemes[lexeme]
		except:
			raise KeyError("'%s' is not a valid lexeme for a %s element" % (lexeme, cls.__name__))

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
			return None

class Diode(Element):
	lexemes = {'»':('ew','»'), '«':('we','«')}

	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)

	@classmethod
	def getFlavor(cls, lexeme):
		try:
			return cls.lexemes[lexeme]
		except:
			raise KeyError("'%s' is not a valid lexeme for a %s element" % (lexeme, cls.__name__))

	def poll(self, side):
		if side == self.flavor[0]:
			return self.pollNeighbor(self.flavor[1])
		else:
			return None

class Empty(Element):
	lexemes = ' '

	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, self.lexemes[0])

class InBit(Element):
	lexemes = 'ABCDEFGH'

	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, lexeme)
		self.index = self.lexemes.index(lexeme)

	def poll(self, side):
		if side in 'nswe':
			return self.board.readBit(self.index)
		else:
			return None

class Memory(Element):
	lexemes = {'M':('ew','M'), 'm':('we','m')}

	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)
		self.currValue = 0
		board.registerInternal(self)

	@classmethod
	def getFlavor(cls, lexeme):
		try:
			return cls.lexemes[lexeme]
		except:
			raise KeyError("'%s' is not a valid lexeme for a %s element" % (lexeme, cls.__name__))

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
			return None

class Not(Element):
	lexemes = {'⌐~':('ew','⌐'), '¬÷':('we','¬')}

	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)

	@classmethod
	def getFlavor(cls, lexeme):
		for key in cls.lexemes:
			if lexeme in key:
				return cls.lexemes[key]
		else:
			raise KeyError("'%s' is not a valid lexeme for a %s element" % (lexeme, cls.__name__))

	def poll(self, side):
		if side == self.flavor[0]:
			return 1 - self.pollNeighbor(self.flavor[1])
		else:
			return None

class Or(Element):
	lexemes = {')':('ew',')'), '(':('we','(')}

	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)

	@classmethod
	def getFlavor(cls, lexeme):
		try:
			return cls.lexemes[lexeme]
		except:
			raise KeyError("'%s' is not a valid lexeme for a %s element" % (lexeme, cls.__name__))

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
			return None

class OutBit(Element):
	lexemes = 'abcdefgh'

	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, lexeme)
		self.index = self.lexemes.index(lexeme)
		board.registerInternal(self)

	def pollInternal(self):
		if self.board.checkStatus(Board.WRITE_HOLD):
			# Optimization - do not perform OutBit polls when WRITE_HOLD
			return
		value = self.pollNeighbor('n') or\
		        self.pollNeighbor('s') or\
		        self.pollNeighbor('w') or\
		        self.pollNeighbor('e')
		self.board.writeBit(self.index, value)

class Pause(Element):
	# pause for muliples of 1 sec, or of 1/256ths of a sec
	lexemes = {'P':(1,'P'), 'p':(1/256,'p')}

	def __init__(self, board, x, y, z, lexeme):
		self.scale, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)
		board.registerInternal(self)

	@classmethod
	def getFlavor(cls, lexeme):
		try:
			return cls.lexemes[lexeme]
		except:
			raise KeyError("'%s' is not a valid lexeme for a %s element" % (lexeme, cls.__name__))

	def pollInternal(self):
		if self.pollNeighbor('n') or\
		   self.pollNeighbor('s') or\
		   self.pollNeighbor('w') or\
		   self.pollNeighbor('e'):
			stack_peek = 0
			for bit in self.board.stackheadr[::-1]:
				stack_peek = (stack_peek << 1) | bit
			self.board.addSleep(stack_peek * self.scale)

class Pin(Element):
	lexemes = 'Oo'

	def __init__(self, board, x, y, z, lexeme):
		lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)

	@classmethod
	def getFlavor(cls, lexeme):
		if lexeme in cls.lexemes:
			return lexeme
		else:
			raise KeyError("'%s' is not a valid lexeme for a %s element" % (lexeme, cls.__name__))


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

class Pulse(Element):
	lexemes = '!'

	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, self.lexemes[0])

	def poll(self, side):
		if side in 'nswe':
			# Zero is the setup age, so pulse at age one.
			if self.board.age == 1:
				return 1
			else:
				return 0
		else:
			return None

class Random(Element):
	lexemes = '?'

	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, self.lexemes[0])
		self.age = 0
		self.value = 0

	def poll(self, side):
		if side in 'nswe':
			if self.age != self.board.age:
				self.value = random.choice([0, 1])
				self.age = self.board.age
			return self.value
		else:
			return None

class Sleep(Element):
	# sleep for 1/10, 1/4, 1/2, or 1 sec.
	lexemes = '$'
	sleep_ramp = [0, 1/10, 1/4, 1/2, 1]

	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, self.lexemes[0])
		board.registerInternal(self)

	def pollInternal(self):
		idx = self.pollNeighbor('n') +\
		      self.pollNeighbor('s') +\
		      self.pollNeighbor('w') +\
		      self.pollNeighbor('e')
		self.board.addSleep(self.sleep_ramp[idx])

class Source(Element):
	lexemes = '*'

	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, self.lexemes[0])

	def poll(self, side):
		if side in 'nswe':
			return 1
		else:
			return None

class StackBit(Element):
	lexemes = '01234567'

	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, lexeme)
		self.index = self.lexemes.index(lexeme)
		board.registerInternal(self)

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
			return None

class StackControl(Element):
	lexemes = {'9':('w','9'), '8':('r','8')}

	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)
		board.registerInternal(self)

	@classmethod
	def getFlavor(cls, lexeme):
		try:
			return cls.lexemes[lexeme]
		except:
			raise KeyError("'%s' is not a valid lexeme for a %s element" % (lexeme, cls.__name__))

	def pollInternal(self):
		value = self.pollNeighbor('n') or\
		        self.pollNeighbor('s') or\
		        self.pollNeighbor('w') or\
		        self.pollNeighbor('e')
		self.board.setStackControl(self, self.flavor, value)

class Switch(Element):
	lexemes = {'/':(1,'/'), '\\':(0,'\\')}

	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)

	@classmethod
	def getFlavor(cls, lexeme):
		try:
			return cls.lexemes[lexeme]
		except:
			raise KeyError("'%s' is not a valid lexeme for a %s element" % (lexeme, cls.__name__))

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
			return None

class Wire(Element):
	lexemes = {'+┼':('nswe','┼'), '|│':('ns','│'), '-─':('ew','─'),
	           '^┴':('nwe','┴'), 'v┬':('swe','┬'), '>├':('nse','├'), '<┤':('nsw','┤'),
	           '`└':('ne','└'), '\'┘':('nw','┘'), ',┌':('se','┌'), '.┐':('sw','┐')}

	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)

	@classmethod
	def getFlavor(cls, lexeme):
		for key in cls.lexemes:
			if lexeme in key:
				return cls.lexemes[key]
		else:
			raise KeyError("'%s' is not a valid lexeme for a %s element" % (lexeme, cls.__name__))

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
			return None

class WireCross(Element):
	lexemes = '×x'

	def __init__(self, board, x, y, z, lexeme):
		Element.__init__(self, board, x, y, z, self.lexemes[0])

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
			return None

class Xor(Element):
	lexemes = {'}':('ew','}'), '{':('we','{')}

	def __init__(self, board, x, y, z, lexeme):
		self.flavor, lex = self.__class__.getFlavor(lexeme)
		Element.__init__(self, board, x, y, z, lex)

	@classmethod
	def getFlavor(cls, lexeme):
		try:
			return cls.lexemes[lexeme]
		except:
			raise KeyError("'%s' is not a valid lexeme for a %s element" % (lexeme, cls.__name__))

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
			return None

###                     ###
#   End Element classes   #
###                     ###

class DummyPrepare(object):
	pass
class DummyFinalize(object):
	pass

PRIORITYLIST = [DummyPrepare,
		StackControl,
		StackBit,
		Memory,
		Sleep,
		Pause,
		Delay,
		Control,
		OutBit,
		Debug,
		DummyFinalize]

# Generate the set of all subclasses of Element
classes = set()
module = sys.modules[__name__]
for itemName in dir(module):
	item = getattr(module, itemName)
	try:
		if issubclass(item, Element) and item is not Element:
			classes.add(item)
		else:
			pass
	except TypeError: # item isn't a class
		pass

# Generate the 1-to-1 mapping of lexeme -> element type
lexmap = {}
lexerrs = []
for cls in classes:
	for lexes in cls.getValidLexemes():
		for lex in lexes:
			prev = lexmap.setdefault(lex, cls)
			if prev != cls:
				lexerrs.append(ValueError("The lexeme '%s' is claimed by both class '%s' and class '%s'."
				                          % (lex, prev.__name__, cls.__name__)))
if lexerrs:
	raise ValueError('\nValueError: '.join(str(err) for err in lexerrs))

# Generate the 1-to-many mapping of element type -> lexeme
lexmap_r = defaultdict(list)
for k, v in lexmap.items():
	lexmap_r[v].append(k)
lexmap_r = dict(lexmap_r)

def getElementType(lexeme):
	try:
		return lexmap[lexeme]
	except KeyError:
		raise KeyError("'%s' is not a valid lexeme" % (lexeme))

if __name__ == '__main__':
	print('This file cannot be executed directly. Please use the chip interpreter instead.')

